# save as check_models.py and run: python check_models.py

from google import genai
import os
from dotenv import load_dotenv

load_dotenv()

client = genai.Client(api_key=os.getenv("AIzaSyCAIs5FWr8kN6g3czDaM0Q-XRl5LpmPXrw"))

print("✅ Models available for your API key:\n")
for model in client.models.list():
    print(f"  {model.name}")