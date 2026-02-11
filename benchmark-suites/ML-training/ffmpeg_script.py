import os
import subprocess
import multiprocessing
import time

def split_video(input_video, segment_time):
    """Split the input video into multiple segments."""
    command = [
        "ffmpeg", "-i", input_video, "-c", "copy", "-map", "0",
        "-segment_time", str(segment_time), "-f", "segment", "segment_%03d.mp4"
    ]
    subprocess.run(command)

def process_segment(segment):
    """Process a video segment with FFmpeg."""
    output_segment = f"processed_{segment}"
    command = [
        "ffmpeg", "-i", segment,
        "-vf", "scale=1920x1080,format=yuv420p",
        "-vcodec", "libx264", "-preset", "veryslow", "-crf", "18", "-threads", "1",
        "-acodec", "aac", "-b:a", "192k", "-y", output_segment
    ]
    subprocess.run(command)

def merge_segments(output_video, num_segments):
    """Merge processed video segments into a single output video."""
    with open("filelist.txt", "w") as filelist:
        for i in range(num_segments):
            filelist.write(f"file 'processed_segment_{i:03d}.mp4'\n")

    command = [
        "ffmpeg", "-f", "concat", "-safe", "0", "-i", "filelist.txt",
        "-c", "copy", output_video
    ]
    subprocess.run(command)

def run_ffmpeg(duration):
    """Runs the FFmpeg encoding process with high CPU utilization."""
    input_video = "input.mp4"
    output_video = "output.mp4"
    segment_time = 60  # Segment duration in seconds

    # Split the video into segments
    split_video(input_video, segment_time)

    # Get the list of video segments
    segments = sorted([f for f in os.listdir() if f.startswith("segment_") and f.endswith(".mp4")])
    num_segments = len(segments)

    # Process each segment in parallel using multiprocessing
    num_cores = multiprocessing.cpu_count()
    with multiprocessing.Pool(processes=num_cores) as pool:
        pool.map(process_segment, segments)

    # Merge the processed segments
    merge_segments(output_video, num_segments)

if __name__ == "__main__":
    duration = 600  # Duration in seconds
    run_ffmpeg(duration)

