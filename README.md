# JD Bot

An AI-powered job description generator that helps create comprehensive and professional job postings using Google's Gemini API.

## Features

- 🤖 AI-powered job posting generation using Gemini
- 💬 Interactive chat interface
- 📝 Automatic information extraction from user input
- 🎯 Smart context understanding
- 🔄 Real-time job posting modifications
- 📍 Location-aware job descriptions
- ⚡ Fast and responsive interface

## Prerequisites

- Python 3.8 or higher
- Google Cloud account with Gemini API access
- API key for Google Gemini

## Setup

1. Clone this repository:
   ```bash
   git clone <your-repository-url>
   cd jd_bot
   ```

2. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Unix/macOS
   # or
   .\venv\Scripts\activate  # On Windows
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Create a `.env` file in the root directory with your Gemini API key:
   ```
   GOOGLE_API_KEY=your_api_key_here
   ```

## Usage

1. Activate your virtual environment:
   ```bash
   source venv/bin/activate  # On Unix/macOS
   # or
   .\venv\Scripts\activate  # On Windows
   ```

2. Start the Flask server:
   ```bash
   python bot.py
   ```

3. Open your browser and navigate to:
   ```
   http://localhost:5001
   ```

## Features in Detail

### Job Posting Generation
- Automatically extracts job role, company, location, and experience requirements
- Generates comprehensive job descriptions with proper sections
- Supports custom modifications and updates

### Chat Interface
- Real-time interaction with the bot
- Typing indicators for better UX
- Support for multi-line input
- Responsive design

### Information Extraction
- Smart parsing of user input
- Context-aware responses
- Maintains conversation history

## Development

To contribute to the project:

1. Fork the repository
2. Create a new branch for your feature
3. Make your changes
4. Run tests:
   ```bash
   pytest test_bot.py
   ```
5. Submit a pull request

## Testing

Run the test suite:
```bash
pytest test_bot.py
```

Test the API connection:
```bash
python test_api.py
```

## Troubleshooting

1. API Key Issues:
   - Ensure your `.env` file exists and contains the correct API key
   - Verify your API key has access to Gemini

2. Installation Issues:
   - Make sure you're using Python 3.8 or higher
   - Try reinstalling dependencies: `pip install -r requirements.txt --force-reinstall`

3. Runtime Errors:
   - Check the console for error messages
   - Verify all required files are in place
   - Ensure proper permissions for file access

## License

MIT License - See LICENSE file for details

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request. For major changes, please open an issue first to discuss what you would like to change.

## Acknowledgments

- Google Gemini API for powering the AI capabilities
- Flask for the web framework
- Contributors and testers 
