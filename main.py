import traceback

from pytubefix import YouTube

try:
    url = "https://www.youtube.com/watch?v=xIkTWaOpiRQ"
    print("Downloading...")
    yt = YouTube(url, client='ANDROID_VR')
    
    # Get highest resolution video stream
    stream = yt.streams.get_highest_resolution()
    stream.download()
    
    print("Download completed!")

except Exception as e:
    print("An error occurred:")
    traceback.print_exc()
