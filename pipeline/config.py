from google import genai


API_KEY = "AIzaSyDBaxT2Boon8uI5G4NTqsOM2H3SD5sRCok"
CHUNK_SIZE = 12000  # characters per chunk
MODEL_NAME = "gemini-3-flash-preview"


client = genai.Client(api_key="API_KEY")

for m in client.models.list():
    print(m.name)


''' models to use:
gemini-3-flash-preview ~50b
gemini-2.5-flash ~5b
gemini-2.5-flash-lite ~1b
'''