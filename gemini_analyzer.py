import os
import google.generativeai as genai

class GeminiAnalyzer:
    def __init__(self, api_key):
        if not api_key:
            raise ValueError("API key cannot be empty.")
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-1.5-pro')

    def analyze_text(self, text):
        try:
            prompt = (
                "Analyze the following text from a financial document (e.g., investor call transcript, annual report). "
                "Identify key financial highlights, significant business developments, risks, and future outlook. "
                "Summarize the most important information concisely and clearly. "
                "If the text is not a financial document or does not contain relevant information, state that."
                f"\n\nText: {text}"
            )
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            return f"Error analyzing text with Gemini: {e}"