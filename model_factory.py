# model_factory.py
import google.generativeai as genai

class ModelFactory:
    def __init__(self, api_key=None):
        self.api_key = api_key
        if self.api_key:
            genai.configure(api_key=self.api_key)

    def get_chat_model(self):
        return genai.GenerativeModel("gemini-2.0-flash")
