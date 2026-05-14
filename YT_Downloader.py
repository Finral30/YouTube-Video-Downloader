import os
import sys
import threading
import subprocess
import re
import customtkinter as ctk

from tkinter import filedialog, messagebox
from urllib.error import HTTPError

# pytubefix
from pytubefix import YouTube
from pytubefix.exceptions import (
    RegexMatchError,
    VideoUnavailable
)

# ---------------- PATH ----------------

DEFAULT_DOWNLOAD_PATH = r"F:\Videos"
os.makedirs(DEFAULT_DOWNLOAD_PATH, exist_ok=True)

if getattr(sys, 'frozen', False):
    BASE_DIR = sys._MEIPASS
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

FFMPEG_PATH = os.path.join(BASE_DIR, "ffmpeg.exe")

# ---------------- CONFIG ----------------

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

cancel_download = False


class DownloadCancelled(Exception):
    pass


# ---------------- FUNCTIONS ----------------

def check_ffmpeg():
    if not os.path.exists(FFMPEG_PATH):
        messagebox.showerror(
            "FFmpeg Error",
            f"ffmpeg.exe not found at:\n{FFMPEG_PATH}"
        )
        return False
    return True


def sanitize_filename(name):
    return re.sub(r'[\\/*?:"<>|]', "", name)


def on_progress(stream, chunk, bytes_remaining):
    global cancel_download

    if cancel_download:
        raise DownloadCancelled("Cancelled")

    total_size = stream.filesize

    if total_size is None or total_size == 0:
        return

    downloaded = total_size - bytes_remaining
    percent = downloaded / total_size

    try:
        app.after(0, progress_bar.set, percent)

        app.after(
            0,
            lambda: status_label.configure(
                text=f"Downloading... {int(percent * 100)}%"
            )
        )
    except:
        pass


def run_ffmpeg(cmd):
    creationflags = 0x08000000 if sys.platform == "win32" else 0

    result = subprocess.run(
        cmd,
        creationflags=creationflags,
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        raise Exception(result.stderr)


def download_video():
    global cancel_download

    cancel_download = False

    if not check_ffmpeg():
        return

    url = url_entry.get().strip()
    quality = quality_var.get()
    download_type = type_var.get()
    bitrate = bitrate_var.get()
    folder = path_var.get()

    if not url:
        messagebox.showerror(
            "Error",
            "Please enter a YouTube URL."
        )
        return

    app.after(0, lambda: start_btn.configure(state="disabled"))
    app.after(0, lambda: cancel_btn.configure(state="normal"))
    app.after(0, lambda: progress_bar.set(0))

    temp_files = []

    try:
        app.after(
            0,
            lambda: status_label.configure(
                text="Fetching video information..."
            )
        )

        # Stable pytubefix setup
        yt = YouTube(
            url,
            on_progress_callback=on_progress,
            use_oauth=False,
            allow_oauth_cache=True
        )

        safe_title = sanitize_filename(yt.title)

        # =========================================================
        # AUDIO DOWNLOAD
        # =========================================================

        if download_type == "Audio":

            app.after(
                0,
                lambda: status_label.configure(
                    text="Finding best audio stream..."
                )
            )

            audio_stream = (
                yt.streams
                .filter(
                    only_audio=True,
                    file_extension='mp4'
                )
                .order_by('abr')
                .desc()
                .first()
            )

            if not audio_stream:
                raise Exception("No audio stream found.")

            temp_audio = os.path.join(
                folder,
                f"temp_audio_{id(yt)}.mp4"
            )

            temp_files.append(temp_audio)

            audio_stream.download(
                output_path=folder,
                filename=os.path.basename(temp_audio)
            )

            if cancel_download:
                raise DownloadCancelled()

            app.after(
                0,
                lambda: status_label.configure(
                    text="Converting to MP3..."
                )
            )

            final_path = os.path.join(
                folder,
                f"{safe_title}.mp3"
            )

            ffmpeg_bitrate = bitrate.replace("kbps", "k")

            cmd = [
                FFMPEG_PATH,
                "-y",
                "-i", temp_audio,
                "-vn",
                "-b:a", ffmpeg_bitrate,
                final_path
            ]

            run_ffmpeg(cmd)

            ext = "mp3"

        # =========================================================
        # VIDEO DOWNLOAD
        # =========================================================

        else:

            app.after(
                0,
                lambda: status_label.configure(
                    text="Finding video stream..."
                )
            )

            # Get adaptive mp4 video streams
            video_streams = yt.streams.filter(
                adaptive=True,
                only_video=True,
                file_extension='mp4'
            )

            # Try exact resolution
            video_stream = video_streams.filter(
                resolution=quality
            ).first()

            # Fallback
            if not video_stream:

                app.after(
                    0,
                    lambda: status_label.configure(
                        text=f"{quality} unavailable, using fallback..."
                    )
                )

                video_stream = (
                    video_streams
                    .order_by('resolution')
                    .desc()
                    .first()
                )

            if not video_stream:
                raise Exception("No video stream found.")

            # Best audio stream
            audio_stream = (
                yt.streams
                .filter(
                    only_audio=True,
                    file_extension='mp4'
                )
                .order_by('abr')
                .desc()
                .first()
            )

            if not audio_stream:
                raise Exception("No audio stream found.")

            temp_video = os.path.join(
                folder,
                f"temp_video_{id(yt)}.mp4"
            )

            temp_audio = os.path.join(
                folder,
                f"temp_audio_{id(yt)}.mp4"
            )

            temp_files.extend([temp_video, temp_audio])

            # Download video
            app.after(
                0,
                lambda: status_label.configure(
                    text="Downloading video..."
                )
            )

            video_stream.download(
                output_path=folder,
                filename=os.path.basename(temp_video)
            )

            if cancel_download:
                raise DownloadCancelled()

            # Download audio
            app.after(
                0,
                lambda: status_label.configure(
                    text="Downloading audio..."
                )
            )

            progress_bar.set(0)

            audio_stream.download(
                output_path=folder,
                filename=os.path.basename(temp_audio)
            )

            if cancel_download:
                raise DownloadCancelled()

            # Merge
            app.after(
                0,
                lambda: status_label.configure(
                    text="Merging video and audio..."
                )
            )

            final_path = os.path.join(
                folder,
                f"{safe_title}.mp4"
            )

            cmd = [
                FFMPEG_PATH,
                "-y",
                "-i", temp_video,
                "-i", temp_audio,
                "-map", "0:v:0",
                "-map", "1:a:0",
                "-c:v", "copy",
                "-c:a", "aac",
                "-strict", "experimental",
                final_path
            ]

            run_ffmpeg(cmd)

            ext = "mp4"

        # =========================================================
        # CLEANUP
        # =========================================================

        for file in temp_files:
            if os.path.exists(file):
                os.remove(file)

        app.after(0, progress_bar.set, 1)

        app.after(
            0,
            lambda: status_label.configure(
                text="Download completed ✅"
            )
        )

        app.after(
            0,
            add_history,
            f"{safe_title}.{ext}"
        )

    # =============================================================
    # ERRORS
    # =============================================================

    except DownloadCancelled:

        app.after(
            0,
            lambda: status_label.configure(
                text="Download cancelled ❌"
            )
        )

    except HTTPError as e:

        app.after(
            0,
            lambda: messagebox.showerror(
                "HTTP Error",
                f"{str(e)}"
            )
        )

        app.after(
            0,
            lambda: status_label.configure(
                text="Download failed ❌"
            )
        )

    except RegexMatchError:

        app.after(
            0,
            lambda: messagebox.showerror(
                "Invalid URL",
                "Invalid YouTube URL."
            )
        )

    except VideoUnavailable:

        app.after(
            0,
            lambda: messagebox.showerror(
                "Unavailable",
                "Video unavailable or age restricted."
            )
        )

    except Exception as e:

        app.after(
            0,
            lambda: messagebox.showerror(
                "Error",
                f"Download failed:\n\n{str(e)}"
            )
        )

        app.after(
            0,
            lambda: status_label.configure(
                text="Download failed ❌"
            )
        )

    finally:

        for file in temp_files:
            try:
                if os.path.exists(file):
                    os.remove(file)
            except:
                pass

        app.after(
            0,
            lambda: start_btn.configure(state="normal")
        )

        app.after(
            0,
            lambda: cancel_btn.configure(state="disabled")
        )


def start_thread():
    threading.Thread(
        target=download_video,
        daemon=True
    ).start()


def cancel():
    global cancel_download
    cancel_download = True


def browse_folder():
    folder = filedialog.askdirectory(
        initialdir=path_var.get()
    )

    if folder:
        path_var.set(folder)


def add_history(name):

    history_box.configure(state="normal")

    if history_box.get("1.0", "end").strip() == "No downloads yet...":
        history_box.delete("1.0", "end")

    history_box.insert("end", name + "\n")

    history_box.configure(state="disabled")


# =========================================================
# UI
# =========================================================

app = ctk.CTk()

app.title("YouTube Downloader")
app.geometry("650x560")
app.resizable(False, False)

ctk.CTkLabel(
    app,
    text="YouTube Downloader",
    font=("Segoe UI", 24, "bold")
).pack(pady=15)

url_entry = ctk.CTkEntry(
    app,
    width=560,
    placeholder_text="Paste YouTube URL here"
)

url_entry.pack(pady=8)

options = ctk.CTkFrame(app)
options.pack(pady=10)

quality_var = ctk.StringVar(value="1080p")

ctk.CTkOptionMenu(
    options,
    variable=quality_var,
    values=[
        "1080p",
        "720p",
        "480p",
        "360p",
        "240p",
        "144p"
    ]
).grid(row=0, column=0, padx=8)

type_var = ctk.StringVar(value="Video")

ctk.CTkOptionMenu(
    options,
    variable=type_var,
    values=[
        "Video",
        "Audio"
    ]
).grid(row=0, column=1, padx=8)

bitrate_var = ctk.StringVar(value="320kbps")

ctk.CTkOptionMenu(
    options,
    variable=bitrate_var,
    values=[
        "320kbps",
        "256kbps",
        "192kbps",
        "160kbps",
        "128kbps"
    ]
).grid(row=0, column=2, padx=8)

path_var = ctk.StringVar(
    value=DEFAULT_DOWNLOAD_PATH
)

ctk.CTkButton(
    app,
    text="Choose Download Folder",
    command=browse_folder
).pack(pady=5)

ctk.CTkLabel(
    app,
    textvariable=path_var,
    font=("Segoe UI", 11)
).pack()

btns = ctk.CTkFrame(app)
btns.pack(pady=15)

start_btn = ctk.CTkButton(
    btns,
    text="Start Download",
    width=160,
    height=40,
    command=start_thread
)

start_btn.grid(row=0, column=0, padx=10)

cancel_btn = ctk.CTkButton(
    btns,
    text="Cancel",
    width=120,
    height=40,
    fg_color="blue",
    command=cancel,
    state="disabled"
)

cancel_btn.grid(row=0, column=1, padx=10)

progress_bar = ctk.CTkProgressBar(
    app,
    width=560
)

progress_bar.set(0)
progress_bar.pack(pady=10)

status_label = ctk.CTkLabel(
    app,
    text="Waiting...",
    font=("Segoe UI", 12)
)

status_label.pack()

ctk.CTkLabel(
    app,
    text="Download History",
    font=("Segoe UI", 14, "bold")
).pack(pady=8)

history_box = ctk.CTkTextbox(
    app,
    width=560,
    height=120
)

history_box.pack()

history_box.insert("end", "No downloads yet...")
history_box.configure(state="disabled")

app.mainloop()