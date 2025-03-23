# Perplexity API Query Script

This Python script demonstrates how to interact with the Perplexity AI API to ask questions and store responses in a Supabase database.

## Setup

1. Install the required dependencies:
```bash
pip install -r requirements.txt
```

2. Create a `.env` file in the root directory and add your API keys:
```bash
PERPLEXITY_API_KEY=your_perplexity_api_key_here
SUPABASE_URL=your_supabase_project_url
SUPABASE_KEY=your_supabase_anon_key
```

You can get your:
- Perplexity API key by signing up at https://www.perplexity.ai/
- Supabase credentials from your Supabase project settings

## Database Schema

The script expects a table named `AI_VOTES` in your Supabase database with the following columns:
- `match_id` (integer)
- `winner_selection` (text)
- `margin_selection` (text)
- `reasoning` (text)

## Usage

Run the script using Python:
```bash
python perplexity_query.py
```

The script will:
1. Ask Perplexity AI about match predictions
2. Process the response into structured data
3. Store the predictions in your Supabase database

## Customization

You can modify the following in the script:
- Change the model by updating the `model` parameter in the payload
- Modify the question in the `main()` function
- Add additional parameters to the API call as needed

## Error Handling

The script includes basic error handling for:
- Missing API keys
- Network request errors
- Invalid responses
- Database insertion errors 