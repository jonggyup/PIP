math.randomseed(os.time())
math.random(); math.random(); math.random()

local function get_user()
  local id = math.random(0, 500)
  local user_name = "Cornell_" .. tostring(id)
  local pass_word = ""
  for i = 0, 9, 1 do
    pass_word = pass_word .. tostring(id)
  end
  return user_name, pass_word
end

local function search_hotel()
  local in_date = math.random(9, 23)
  local out_date = math.random(in_date + 1, 24)

  local in_date_str = "2015-04-" .. (in_date < 10 and "0" or "") .. tostring(in_date)
  local out_date_str = "2015-04-" .. (out_date < 10 and "0" or "") .. tostring(out_date)

  local lat = 38.0235 + (math.random(0, 481) - 240.5) / 1000.0
  local lon = -122.095 + (math.random(0, 325) - 157.0) / 1000.0

  local method = "GET"
  local path = url .. "/hotels?inDate=" .. in_date_str ..
    "&outDate=" .. out_date_str .. "&lat=" .. tostring(lat) .. "&lon=" .. tostring(lon)

  local headers = {}
  return wrk.format(method, path, headers, nil)
end

local function recommend()
  local coin = math.random()
  local req_param = ""
  if coin < 0.33 then
    req_param = "dis"
  elseif coin < 0.66 then
    req_param = "rate"
  else
    req_param = "price"
  end
end
