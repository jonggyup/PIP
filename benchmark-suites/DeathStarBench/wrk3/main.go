// wrk3: closed-loop HTTP load with demand fluctuation + goodput + headers
package main

import (
	"bufio"
	"context"
	"crypto/tls"
	"encoding/csv"
	"flag"
	"fmt"
	"io"
	"math"
	"math/rand"
	"net"
	"net/http"
	"os"
	"runtime"
	"sort"
	"strconv"
	"strings"
	"sync"
	"sync/atomic"
	"time"
)

// -------- simple histogram for percentiles (microseconds) --------
type hdrHist struct {
	mu   sync.Mutex
	data []int64
}

func (h *hdrHist) add(us int64) { h.mu.Lock(); h.data = append(h.data, us); h.mu.Unlock() }
func (h *hdrHist) reset()       { h.mu.Lock(); h.data = h.data[:0]; h.mu.Unlock() }
func (h *hdrHist) pct(p float64) float64 {
	h.mu.Lock()
	n := len(h.data)
	if n == 0 {
		h.mu.Unlock()
		return 0
	}
	cp := make([]int64, n)
	copy(cp, h.data)
	h.mu.Unlock()
	sort.Slice(cp, func(i, j int) bool { return cp[i] < cp[j] })
	idx := int(math.Ceil(p*float64(n)) - 1)
	if idx < 0 {
		idx = 0
	}
	if idx >= n {
		idx = n - 1
	}
	return float64(cp[idx]) / 1000.0 // ms
}

// -------- demand profiles --------
type phase struct {
	dur   time.Duration
	conns int
}

func parsePhases(s string) ([]phase, error) {
	if strings.TrimSpace(s) == "" {
		return nil, nil
	}
	parts := strings.Split(s, ",")
	out := make([]phase, 0, len(parts))
	for _, p := range parts {
		p = strings.TrimSpace(p)
		sub := strings.Split(p, "@")
		if len(sub) != 2 {
			return nil, fmt.Errorf("invalid phase %q (want DUR@CONNS)", p)
		}
		dur, err := time.ParseDuration(strings.TrimSpace(sub[0]))
		if err != nil {
			return nil, fmt.Errorf("phase %q duration: %v", p, err)
		}
		c, err := strconv.Atoi(strings.TrimSpace(sub[1]))
		if err != nil || c < 0 {
			return nil, fmt.Errorf("phase %q conns: %v", p, err)
		}
		out = append(out, phase{dur: dur, conns: c})
	}
	return out, nil
}

type sineSpec struct {
	enabled bool
	period  time.Duration
	low     int
	high    int
}

func parseSine(s string) (sineSpec, error) {
	spec := sineSpec{}
	if strings.TrimSpace(s) == "" {
		return spec, nil
	}
	spec.enabled = true
	for _, kv := range strings.Split(s, ",") {
		kv = strings.TrimSpace(kv)
		if kv == "" {
			continue
		}
		p := strings.SplitN(kv, "=", 2)
		if len(p) != 2 {
			return spec, fmt.Errorf("invalid sine token %q", kv)
		}
		k, v := strings.ToLower(strings.TrimSpace(p[0])), strings.TrimSpace(p[1])
		switch k {
		case "period":
			d, err := time.ParseDuration(v)
			if err != nil {
				return spec, fmt.Errorf("sine.period: %v", err)
			}
			spec.period = d
		case "low":
			x, err := strconv.Atoi(v)
			if err != nil {
				return spec, fmt.Errorf("sine.low: %v", err)
			}
			spec.low = x
		case "high":
			x, err := strconv.Atoi(v)
			if err != nil {
				return spec, fmt.Errorf("sine.high: %v", err)
			}
			spec.high = x
		default:
			return spec, fmt.Errorf("unknown sine key %q", k)
		}
	}
	if spec.period <= 0 || spec.low < 0 || spec.high <= spec.low {
		return spec, fmt.Errorf("sine requires period>0 and 0<=low<high")
	}
	return spec, nil
}

func clip(n, lo, hi int) int {
	if n < lo {
		return lo
	}
	if n > hi {
		return hi
	}
	return n
}

func loadTrace(path string) ([]int, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer f.Close()
	r := csv.NewReader(bufio.NewReader(f))
	r.FieldsPerRecord = -1
	var out []int
	line := 0
	for {
		rec, e := r.Read()
		if e == io.EOF {
			break
		}
		if e != nil {
			return nil, fmt.Errorf("trace read error line %d: %v", line+1, e)
		}
		line++
		if len(rec) == 0 {
			continue
		}
		// optional header
		if line == 1 {
			if _, err := strconv.Atoi(strings.TrimSpace(rec[0])); err != nil {
				continue
			}
		}
		if len(rec) < 2 {
			return nil, fmt.Errorf("trace line %d: need 2 columns (second,concurrency)", line)
		}
		conStr := strings.TrimSpace(rec[1])
		c, err := strconv.Atoi(conStr)
		if err != nil {
			return nil, fmt.Errorf("trace line %d: bad concurrency %q", line, conStr)
		}
		if c < 0 {
			c = 0
		}
		out = append(out, c)
	}
	return out, nil
}

// -------- repeatable -header flag --------
type multiFlag []string

func (m *multiFlag) String() string { return strings.Join(*m, "; ") }
func (m *multiFlag) Set(v string) error {
	*m = append(*m, v)
	return nil
}

// -------- main --------
func main() {
	var (
		target     string
		method     string
		body       string
		timeout    time.Duration
		duration   time.Duration
		slaMS      int
		insecure   bool
		maxCPU     int

		phasesStr   string
		phaseLoops  int
		sineStr     string
		traceFile   string
		jitterPct   int
		thinkMeanMS int
		maxPool     int

		headers multiFlag
	)

	flag.StringVar(&target, "target", "", "HTTP(S) URL (incl. query if needed)")
	flag.StringVar(&method, "method", "GET", "HTTP method (GET/POST/PUT)")
	flag.StringVar(&body, "body", "", "Request body for non-GET (form or JSON)")
	flag.DurationVar(&timeout, "timeout", 3*time.Second, "Per-request timeout")
	flag.DurationVar(&duration, "duration", 5*time.Minute, "Overall test duration")
	flag.IntVar(&slaMS, "sla-ms", 50, "SLA threshold in milliseconds for goodput")
	flag.BoolVar(&insecure, "insecure", true, "Skip TLS verification")
	flag.IntVar(&maxCPU, "max-cpu", 0, "GOMAXPROCS limit (0 = all cores)")

	flag.StringVar(&phasesStr, "phases", "", "Comma list DUR@CONNS (e.g., '30s@128,10s@1024'). Repeats with -phase-loops.")
	flag.IntVar(&phaseLoops, "phase-loops", 0, "Repeat -phases this many times (0=no repeat)")
	flag.StringVar(&sineStr, "sine", "", "Sinusoidal concurrency: 'period=60s,low=64,high=2048' (ignored if -trace or -phases).")
	flag.StringVar(&traceFile, "trace", "", "CSV with per-second concurrency: 'second,concurrency' (overrides phases/sine).")
	flag.IntVar(&jitterPct, "jitter-pct", 0, "Per-second +/- jitter percentage on target concurrency (0..50)")
	flag.IntVar(&thinkMeanMS, "think-mean-ms", 0, "Exponential mean think-time per request in ms (0=off)")
	flag.IntVar(&maxPool, "max-pool", 8192, "Max worker pool size (upper bound for concurrency)")

	flag.Var(&headers, "header", "HTTP header 'Key: Value' (repeatable)")

	flag.Parse()

	if target == "" {
		fmt.Fprintln(os.Stderr, "ERROR: -target is required")
		os.Exit(2)
	}
	if maxCPU > 0 {
		runtime.GOMAXPROCS(maxCPU)
	}
	if jitterPct < 0 {
		jitterPct = 0
	}
	if jitterPct > 50 {
		jitterPct = 50
	}

	// HTTP client with keep-alive
	tr := &http.Transport{
		MaxIdleConns:          16384,
		MaxConnsPerHost:       0,
		MaxIdleConnsPerHost:   16384,
		IdleConnTimeout:       90 * time.Second,
		DialContext:           (&net.Dialer{Timeout: 2 * time.Second, KeepAlive: 60 * time.Second}).DialContext,
		TLSClientConfig:       &tls.Config{InsecureSkipVerify: insecure}, //nolint:gosec
		ForceAttemptHTTP2:     true,
		DisableCompression:    false,
		ExpectContinueTimeout: 0,
	}
	client := &http.Client{Transport: tr, Timeout: timeout}

	// Demand profile selection
	var useTrace bool
	var traceConns []int
	if traceFile != "" {
		tc, err := loadTrace(traceFile)
		if err != nil {
			fmt.Fprintf(os.Stderr, "ERROR loading -trace: %v\n", err)
			os.Exit(2)
		}
		traceConns = tc
		useTrace = true
	}

	phases, err := parsePhases(phasesStr)
	if err != nil {
		fmt.Fprintf(os.Stderr, "ERROR parsing -phases: %v\n", err)
		os.Exit(2)
	}
	sine, err := parseSine(sineStr)
	if err != nil {
		fmt.Fprintf(os.Stderr, "ERROR parsing -sine: %v\n", err)
		os.Exit(2)
	}
	if !useTrace && len(phases) == 0 && !sine.enabled {
		// default profile (moderate realism)
		def := "20s@128,15s@1024,25s@256,10s@2048,30s@384"
		phases, _ = parsePhases(def)
		phaseLoops = 1
	}

	ctx, cancel := context.WithTimeout(context.Background(), duration)
	defer cancel()
	rand.Seed(time.Now().UnixNano())

	// Metrics
	var totalReq, totalGood uint64
	var winReq, winGood uint64
	var activeConns int64
	var hist hdrHist
	slaUS := int64(slaMS) * 1000

	// Worker pool (full pool started; activation controlled by activeConns)
	wg := &sync.WaitGroup{}
	worker := func(id int) {
		defer wg.Done()
		methodUpper := strings.ToUpper(method)
		var reqBodySrc string
		if methodUpper != "GET" && body != "" {
			reqBodySrc = body
		}
		for {
			select {
			case <-ctx.Done():
				return
			default:
			}
			if int64(id) >= atomic.LoadInt64(&activeConns) {
				time.Sleep(10 * time.Millisecond)
				continue
			}

			var reqBody io.Reader
			if reqBodySrc != "" {
				reqBody = strings.NewReader(reqBodySrc)
			}
			req, err := http.NewRequestWithContext(ctx, methodUpper, target, reqBody)
			if err != nil {
				time.Sleep(5 * time.Millisecond)
				continue
			}
			// apply headers
			for _, h := range headers {
				if i := strings.Index(h, ":"); i > 0 {
					k := strings.TrimSpace(h[:i])
					v := strings.TrimSpace(h[i+1:])
					if k != "" {
						req.Header.Set(k, v)
					}
				}
			}

			start := time.Now()
			resp, err := client.Do(req)
			latUS := time.Since(start).Microseconds()
			atomic.AddUint64(&totalReq, 1)
			atomic.AddUint64(&winReq, 1)
			hist.add(latUS)

			if err == nil {
				io.Copy(io.Discard, resp.Body)
				resp.Body.Close()
				if resp.StatusCode >= 200 && resp.StatusCode < 300 && latUS <= slaUS {
					atomic.AddUint64(&totalGood, 1)
					atomic.AddUint64(&winGood, 1)
				}
			}

			// exponential think-time
			if thinkMeanMS > 0 {
				u := rand.Float64()
				if u <= 1e-12 {
					u = 1e-12
				}
				sleep := time.Duration(-math.Log(u) * float64(thinkMeanMS) * 1e6)
				time.Sleep(sleep)
			}
		}
	}
	for i := 0; i < maxPool; i++ {
		wg.Add(1)
		go worker(i)
	}

	// Controller: sets activeConns each second
	ctrlDone := make(chan struct{})
	go func() {
		defer close(ctrlDone)
		t0 := time.Now()
		ticker := time.NewTicker(1 * time.Second)
		defer ticker.Stop()

		usePhases := !useTrace && len(phases) > 0
		phaseIdx := 0
		phaseLeft := time.Duration(0)
		loopsLeft := phaseLoops
		nextTarget := 0
		if usePhases {
			nextTarget = phases[0].conns
			phaseLeft = phases[0].dur
		}
		tracePos := 0

		for {
			select {
			case now := <-ticker.C:
				if useTrace {
					if tracePos < len(traceConns) {
						nextTarget = traceConns[tracePos]
						tracePos++
					}
				} else if usePhases {
					phaseLeft -= time.Second
					if phaseLeft <= 0 {
						phaseIdx++
						if phaseIdx >= len(phases) {
							if loopsLeft > 0 {
								loopsLeft--
								phaseIdx = 0
							} else {
								phaseIdx = len(phases) - 1
							}
						}
						phaseLeft = phases[phaseIdx].dur
					}
					nextTarget = phases[phaseIdx].conns
				} else if sine.enabled {
					elapsed := now.Sub(t0)
					frac := math.Sin(2 * math.Pi * float64(elapsed%vToDur(sine.period)) / float64(sine.period))
					mid := 0.5 * float64(sine.low+sine.high)
					amp := 0.5 * float64(sine.high-sine.low)
					nextTarget = int(mid + amp*frac)
				}

				// jitter on concurrency
				if jitterPct > 0 && nextTarget > 0 {
					delta := int(math.Round(float64(nextTarget) * float64(jitterPct) / 100.0))
					j := rand.Intn(2*delta+1) - delta // [-delta, +delta]
					nextTarget += j
				}
				nextTarget = clip(nextTarget, 0, maxPool)
				atomic.StoreInt64(&activeConns, int64(nextTarget))
			case <-ctx.Done():
				return
			}
		}
	}()

	// Reporter
	tick := time.NewTicker(1 * time.Second)
	defer tick.Stop()
	fmt.Printf("# time(s), active_conns, rps, goodput_rps(sla<=%dms), p50_ms, p95_ms, p99_ms\n", slaMS)
	startWall := time.Now()
	for {
		select {
		case <-ctx.Done():
			elapsed := time.Since(startWall).Seconds()
			tr := atomic.LoadUint64(&totalReq)
			tg := atomic.LoadUint64(&totalGood)
			p50 := hist.pct(0.50)
			p95 := hist.pct(0.95)
			p99 := hist.pct(0.99)

			// print final line of the time series
			fmt.Printf("%.0f, %d, %.1f, %.1f, %.2f, %.2f, %.2f\n",
				elapsed, atomic.LoadInt64(&activeConns),
				float64(tr)/elapsed, float64(tg)/elapsed, p50, p95, p99)

			wg.Wait()
			<-ctrlDone

			// Summary
			gRatio := 0.0
			if tr > 0 {
				gRatio = float64(tg) / float64(tr)
			}
			fmt.Printf("\nSUMMARY\n")
			fmt.Printf("duration_s: %.0f\n", elapsed)
			fmt.Printf("total_requests: %d\n", tr)
			fmt.Printf("total_good: %d\n", tg)
			fmt.Printf("avg_rps: %.2f\n", float64(tr)/elapsed)
			fmt.Printf("avg_goodput_rps: %.2f\n", float64(tg)/elapsed)
			fmt.Printf("goodput_ratio: %.4f\n", gRatio)
			return

		case <-tick.C:
			wr := atomic.SwapUint64(&winReq, 0)
			wg_ := atomic.SwapUint64(&winGood, 0)
			p50 := hist.pct(0.50)
			p95 := hist.pct(0.95)
			p99 := hist.pct(0.99)
			fmt.Printf("%.0f, %d, %d, %d, %.2f, %.2f, %.2f\n",
				time.Since(startWall).Seconds(), atomic.LoadInt64(&activeConns),
				wr, wg_, p50, p95, p99)
			hist.reset()
		}
	}
}

func vToDur(d time.Duration) time.Duration { return d }

