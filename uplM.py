import os
import pickle
import asyncio
import math
import random
import ffmpeg
import numpy as np
from PIL import Image, ImageDraw
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

def randomName(length):
	s = ""
	for _ in range(length):
		s += chr(random.randint(61, 122))
	s += ".mp4"
	return s

def randomWord(syllables=1):
	parts = []
	sounds = ["ba","be","bi","bo","bu","la","le","li","lo","lu","ra","re","ri","ro","ru","ma","me","mi","mo","na","ne","ni","no","ta","te","ti","to"]
	for _ in range(syllables):
		parts.append(random.choice(sounds))
	word = "".join(parts)
	return word

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
FRAME_COUNT = 250
SIZE = 500

def authenticate():
	creds = None
	if os.path.exists("token.pickle"):
		with open("token.pickle", "rb") as token:
			creds = pickle.load(token)

	if not creds or not creds.valid:
		if creds and creds.expired and creds.refresh_token:
			creds.refresh(Request())
		else:
			from google_auth_oauthlib.flow import Flow
			flow = Flow.from_client_secrets_file(
				'credentials.json',
				scopes=SCOPES,
				redirect_uri='urn:ietf:wg:oauth:2.0:oob'
			)
			auth_url, _ = flow.authorization_url(prompt='consent')
			print("Open this URL in your browser and authorize:")
			print(auth_url)
			code = input("Enter the authorization code here: ")
			flow.fetch_token(code=code)
			creds = flow.credentials
		with open("token.pickle", "wb") as token:
			pickle.dump(creds, token)

	return build("youtube", "v3", credentials=creds)

vertices = np.array([
	[-1, -1, -1],  # base corner 0
	[ 1, -1, -1],  # base corner 1
	[ 1, -1,  1],  # base corner 2
	[-1, -1,  1],  # base corner 3
	[ 0,  1,  0]   # apex
])

faces = [
	(0,1,2,3),  # base
	(0,1,4),    # side 1
	(1,2,4),    # side 2
	(2,3,4),    # side 3
	(3,0,4)     # side 4
]

colors = [
	(random.randint(0,255), random.randint(0,255), random.randint(0,255)),
	(random.randint(0,255), random.randint(0,255), random.randint(0,255)),
	(random.randint(0,255), random.randint(0,255), random.randint(0,255)),
	(random.randint(0,255), random.randint(0,255), random.randint(0,255))
]

def rotate_y(vertices, angle):
	c, s = math.cos(angle), math.sin(angle)
	rot = np.array([
		[ c, 0, s],
		[ 0, 1, 0],
		[-s, 0, c]
	])
	return vertices @ rot.T

def project(v, size, scale=150):
	x, y, z = v
	f = scale / (z + 4)
	return (int(size/2 + x*f), int(size/2 - y*f))

def draw_pyramid(angle, colors):
	img = Image.new("RGB", (SIZE, SIZE), "black")
	draw = ImageDraw.Draw(img)

	verts = rotate_y(vertices, angle)
	proj = [project(v, SIZE) for v in verts]

	for face, color in zip(faces, colors):
		pts = [proj[i] for i in face]
		draw.polygon(pts, fill=color, outline="white")

	return np.array(img)

title = randomName(7)

def generate_video():
	process = (
		ffmpeg
		.input('pipe:', format='rawvideo', pix_fmt='rgb24', s=f'{SIZE}x{SIZE}', r=25)
		.output(title, vcodec='libx264', pix_fmt='yuv420p')
		.overwrite_output()
		.run_async(pipe_stdin=True)
	)
	
	for i in range(FRAME_COUNT):
		angle = i * 2 * math.pi / FRAME_COUNT
		frame_array = draw_pyramid(angle, colors)
		process.stdin.write(frame_array.astype(np.uint8).tobytes())
	
	process.stdin.close()
	process.wait()
	print("Video written to:", title)

def upload_video():
	youtube = authenticate()
	request = youtube.videos().insert(
		part="snippet,status",
		body={
			"snippet": {
				"title": title + " #" + randomWord(5),
				"description": "",
				"tags": ""
			},
			"status": {"privacyStatus": "public"}
		},
		media_body=MediaFileUpload(title, chunksize=-1, resumable=True)
	)

	response = None
	while response is None:
		status, response = request.next_chunk()
		if status:
			print(f"Uploading... {int(status.progress() * 100)}%")

	print("Upload complete! Video ID:", response["id"])

def upl():
	try:
		generate_video()
		upload_video()
		os.remove(title)
	except:
		os.remove(title);

if __name__ == "__main__":
	upl()
