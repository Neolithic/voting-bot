"""
This script is used to query Perplexity API for answers to questions and store results in Supabase.
"""
import os
import requests
from datetime import datetime, timedelta
import pytz
from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI
from output_models import AI_Agent_Vote
from utils import get_supabase_client

def create_agent_structured_output(llm, 
    output_structure,):
    """
    Create an agent with structured output.
    """

    system_message = """You are given predictions from an AI agent. Structure the response to output schema.
Remove any references quoted like [1], [2], etc. in the reasoning.
For winner selection, keep name of the team as in the question. That is abbreviated name of the team.
For margin selection, responsd with A, B, C, or D as in the question.
Give detailed reasoning for the winner selection and margin selection.
Also, do not give your estimated probability of each option for both questions (winner and margin).
"""

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system_message),
            MessagesPlaceholder(variable_name="messages"),
        ]
    )

    llm_chain = llm.with_structured_output(output_structure, strict=True)

    output = prompt | llm_chain

    return output

def insert_vote_to_supabase(match_id, winner_selection, margin_selection, reasoning):
    """
    Insert vote data into Supabase AI_VOTES table.
    """
    supabase = get_supabase_client()
    
    data = {
        'match_id': match_id,
        'winner_selection': winner_selection,
        'margin_selection': margin_selection,
        'reasoning': reasoning
    }
    
    votes_data = [{
        'match_id': match_id,
        'user_email': 'predictorai01@gmail.com',
        'user_name': 'AI Predictor',
        'poll_type': 'winner',
        'option_voted': winner_selection,
        'created_timestamp': datetime.now(pytz.UTC).isoformat()
    },
    {
        'match_id': match_id,
        'user_email': 'predictorai01@gmail.com',
        'user_name': 'AI Predictor',
        'poll_type': 'victory_margin',
        'option_voted': margin_selection,
        'created_timestamp': datetime.now(pytz.UTC).isoformat()
    }
    ]
    try:
        result = supabase.table('AI_VOTES').insert(data).execute()

        for vote in votes_data:
            supabase.table('VOTES').insert(vote).execute()

        print("Successfully inserted vote into Supabase")
        return result
    

    except Exception as e:
        print(f"Error inserting into Supabase: {str(e)}")
        raise

# Load environment variables
load_dotenv()

def ask_perplexity(question):
    """
    Ask Perplexity API for an answer to a question.
    """
    # Get API key from environment variable
    api_key = os.getenv('PERPLEXITY_API_KEY')
    if not api_key:
        raise ValueError("Please set the PERPLEXITY_API_KEY environment variable")

    # API endpoint
    url = "https://api.perplexity.ai/chat/completions"

    # Request headers
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    # Request payload
    payload = {
        "model": "sonar-reasoning-pro",  # You can change the model as needed
        "messages": [
            {
                "role": "user",
                "content": question
            }
        ]
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=300)
        response.raise_for_status()  # Raise an exception for bad status codes
        
        result = response.json()
        return result['choices'][0]['message']['content']
    
    except requests.exceptions.RequestException as e:
        return f"Error making request: {str(e)}"

def get_next_match_without_ai_perspective():
    """
    Get the next match from MATCHES table that doesn't have an AI perspective yet.
    """
    supabase = get_supabase_client()
    
    # Get current time in UTC
    current_time = datetime.now(pytz.UTC)
    # Get time 24 hours from now
    future_time = current_time + timedelta(hours=24)
    
    # Query to get matches that:
    # 1. Are in the next 24 hours
    # 2. Don't have an AI perspective yet
    query = supabase.table('MATCHES').select('*').gte('Poll_Close_Time', current_time.isoformat()).lte('Poll_Close_Time', future_time.isoformat())
    
    # Get all matches in this time range
    matches = query.execute()
    
    if not matches.data:
        raise ValueError("No matches found in the next 24 hours")
    
    # For each match, check if it has an AI perspective
    for match in matches.data:
        # Check if there's an AI vote for this match
        ai_vote = supabase.table('AI_VOTES').select('*').eq('match_id', match['Match_ID']).execute()
        
        if not ai_vote.data:
            return match
    
    raise ValueError("No matches found without AI perspective in the next 24 hours")

def main():
    # Get the next match that needs AI perspective
    match = get_next_match_without_ai_perspective()
    
    match_id = match['Match_ID']
    match_teams = f"{match['Team_1']} vs {match['Team_2']}"
    
    match_date = match['Date']

    question = f"""Answer two questions related to Match No {match_id}: {match_teams} on {match_date}.
Question 1: who will win the match?
Question 2: What will be the victory margin? Your options are:\n
Option A: 0-10 runs / 4 or less balls remaining
Option B: 11-20 runs / 5-9 balls remaining
Option C: 21-35 runs / 10-14 balls remaining
Option D: 36+ runs / 15+ balls remaining

Take into account the current form of the teams, the pitch, and the weather conditions.
Also, take into account team composition, players experience in IPL and on the ground where match is being played.

Think step by step and reason out your answer. For example, for victory margin, think about expected scores of the teams.

Also, tell your estimated probability of each option for both questions (winner and margin).
"""

    print("Asking Perplexity:", question)
    print("\nResponse:")
    response = ask_perplexity(question)
    print(response)
    openai_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, max_tokens=8192)

    agent = create_agent_structured_output(openai_llm, 
        output_structure=AI_Agent_Vote)

    final_response = agent.invoke({"messages": [{"role": "user", "content": 
                f"Question: {question}\n"
                f"Response from AI Agent: {response}"}]})

    print(final_response)
    
    # Insert the response into Supabase
    insert_vote_to_supabase(
        match_id=match_id,
        winner_selection=final_response.winner_selection,
        margin_selection=final_response.margin_selection,
        reasoning=final_response.reasoning
    )



if __name__ == "__main__":
    main() 
