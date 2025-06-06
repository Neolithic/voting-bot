"""
Script to calculate winners and losers based on match results and votes.
"""
from collections import defaultdict

from dotenv import load_dotenv
from utils import get_supabase_client

# Load environment variables
load_dotenv()

def set_valid_to_false(supabase, match_id, poll_type):
    """Set the is_valid flag to false for a given match_id and poll_type."""
    try:
        response = supabase.table('VOTING_RESULTS')\
            .update({'is_valid': False})\
            .eq('match_id', match_id)\
            .eq('poll_type', poll_type)\
            .execute()
        print("Setting these rows as invalid: ", response.data)
    except Exception as e:
        print(f"Error setting is_valid to false for match {match_id}, poll type {poll_type}: {str(e)}")
        raise

def get_unprocessed_matches(supabase):
    """Get match results that haven't been processed in VOTING_RESULTS table."""
    try:
        # First get all match_id and poll_type combinations from VOTING_RESULTS
        processed = supabase.rpc("get_processed_matches").execute()

        # Create a set of processed (match_id, poll_type) tuples
        processed_set = {
            (item['match_id'], item['poll_type'])
            for item in processed.data
        }

        # Get all results
        results = supabase.table('RESULTS').select('*').execute()

        #also get incorrect VOTING_RESULTS matches.
        #incorrect is defined as if there if any match_id, user_email, poll_type
        # combination that had multiple rows valid
        incorrect_results = supabase.rpc('get_invalid_voting_results_polls').execute()
        incorrect_results_set = {
            (item['match_id'], item['poll_type'])
            for item in incorrect_results.data
        }

        for match_id, poll_type in incorrect_results_set:
            set_valid_to_false(supabase, match_id, poll_type)

        # Filter out results that have already been processed
        unprocessed_results = []
        for result in results.data:
            match_id = result['match_id']
            poll_type = result['poll_type']

            if (match_id, poll_type) not in processed_set or (match_id, poll_type) in incorrect_results_set:
                unprocessed_results.append({
                    'match_id': match_id,
                    'poll_type': poll_type,
                    'correct_option': result['result']
                })

        return unprocessed_results
    except Exception as e:
        print(f"Error fetching unprocessed match results: {str(e)}")
        raise

def get_eligible_users(supabase, match_id):
    """Get all users who are eligible to vote for a given match."""
    try:
        response = supabase.table('USERS')\
            .select('user_email')\
            .lte('starting_match_id', match_id)\
            .or_('last_match_id.is.null,last_match_id.gte.' + str(match_id))\
            .execute()

        return [user['user_email'] for user in response.data]
    except Exception as e:
        print(f"Error fetching eligible users for match {match_id}: {str(e)}")
        raise

def get_eligible_users_adhoc_polls(supabase, match_id, poll_type):
    """Get all users for adhoc polls"""

    response = supabase.table('VOTES')\
            .select('user_email')\
            .eq('match_id', match_id)\
            .eq('poll_type', poll_type)\
            .execute()

    if response.data:
        all_users = [vote['user_email'] for vote in response.data]
        return list(set(all_users))

    raise ValueError(f"No users found for adhoc poll {match_id}, poll type {poll_type}")

def get_adhoc_poll_type(supabase, match_id):
    """Get the poll type for an adhoc poll"""
    response = supabase.table('ADHOC_POLLS')\
        .select('poll_type, match_id')\
        .eq('match_id', match_id)\
        .execute()

    if response.data:
        poll_types = [poll['poll_type'] for poll in response.data]
        return list(set(poll_types))

    return []

def get_latest_votes(supabase, match_id, poll_type):
    """
    Get the latest vote for each eligible user for a specific match and poll type.
    Users who haven't voted are counted as losses.
    """
    try:

        adhoc_poll_types = get_adhoc_poll_type(supabase, match_id)

        if poll_type in adhoc_poll_types:
            eligible_users = get_eligible_users_adhoc_polls(supabase, match_id, poll_type)
        else:
            eligible_users = get_eligible_users(supabase, match_id)

        latest_votes = {user_email: None for user_email in eligible_users}

        # Query votes for the specific match and poll type, ordered by created_timestamp
        response = supabase.table('VOTES')\
            .select('user_email, option_voted, created_timestamp')\
            .eq('match_id', match_id)\
            .eq('poll_type', poll_type)\
            .order('created_timestamp', desc=True)\
            .execute()

        # Update with actual votes for users who voted
        for vote in response.data:
            user_email = vote['user_email']
            if user_email in latest_votes and latest_votes[user_email] is None:  # Only keep the first (latest) vote
                latest_votes[user_email] = vote['option_voted']
        
        return latest_votes
    except Exception as e:
        print(f"Error fetching votes for match {match_id}, poll type {poll_type}: {str(e)}")
        raise

def get_amount_per_vote(supabase, match_id, poll_type):
    """Get the amount per vote for a given match."""

    adhoc_poll_types = get_adhoc_poll_type(supabase, match_id)

    if poll_type in adhoc_poll_types:
        return 50

    response = supabase.table('MATCHES')\
            .select('amount_per_poll')\
            .eq('Match_ID', match_id)\
            .execute()

    if response.data and len(response.data) == 1:
        return response.data[0]['amount_per_poll']

    raise ValueError(f"No amount per vote found for match {match_id}")

def calculate_points(correct_option, votes, match_id, poll_type, supabase):
    """
    Calculate points for each user based on their votes.
    Returns dictionaries for winners and losers with their points.
    Pot size is calculated as: number of actual votes * 25
    """

    #get amount per vote from supabase
    amount_per_vote = get_amount_per_vote(supabase, match_id, poll_type)

    POINTS_PER_VOTE = amount_per_vote   # Each vote contributes 25 points to the pot
    LOSS_POINTS = -amount_per_vote      # Points lost on incorrect vote or no vote
    
    winners = {}
    losers = {}
    
      
    # Calculate pot size based on number of actual votes
    pot_size = len(votes) * POINTS_PER_VOTE
    
    # Count winners (only those who actually voted correctly)
    num_winners = sum(1 for vote in votes.values() if vote == correct_option)
    
    # Calculate points per winner (if any)
    points_per_winner = pot_size / num_winners if num_winners > 0 else 0
    
    # Assign points
    for user_id, vote in votes.items():
        if vote == correct_option:
            winners[user_id] = points_per_winner + LOSS_POINTS
        else:
            # Both incorrect votes and no votes (None) count as losses
            losers[user_id] = LOSS_POINTS

    return winners, losers

def store_voting_results(supabase, match_id, poll_type, winners, losers):
    """Store the voting results in the VOTING_RESULTS table."""
    try:
        # Prepare data for winners
        winner_entries = [
            {
                'match_id': match_id,
                'poll_type': poll_type,
                'user_email': user_email,
                'amount': points,
                'is_valid': True
            }
            for user_email, points in winners.items()
        ]
        
        # Prepare data for losers
        loser_entries = [
            {
                'match_id': match_id,
                'poll_type': poll_type,
                'user_email': user_email,
                'amount': points,
                'is_valid': True
            }
            for user_email, points in losers.items()
        ]
        
        # Combine all entries
        all_entries = winner_entries + loser_entries
        
        # Insert into VOTING_RESULTS table
        if all_entries:
            supabase.table('VOTING_RESULTS').insert(all_entries).execute()
            print(f"Stored results for match {match_id}, poll type {poll_type}")
    
    except Exception as e:
        print(f"Error storing voting results: {str(e)}")
        raise

def main():
    supabase = get_supabase_client()

    # Get unprocessed match results
    unprocessed_results = get_unprocessed_matches(supabase)

    if not unprocessed_results:
        print("No new matches to process.")
        return

    # Store all points per user
    total_points = defaultdict(int)

    # Process each unprocessed result
    for result in unprocessed_results:
        match_id = result['match_id']
        poll_type = result['poll_type']
        correct_option = result['correct_option']

        # Get votes and calculate points
        votes = get_latest_votes(supabase, match_id, poll_type)
        winners, losers = calculate_points(correct_option, votes, match_id, 
                                           poll_type, supabase)

        # Store results in VOTING_RESULTS table
        store_voting_results(supabase, match_id, poll_type, winners, losers)

        # Update total points
        for user_id, points in winners.items():
            total_points[user_id] += points
        for user_id, points in losers.items():
            total_points[user_id] += points

        # Print results for this match and poll type
        print(f"\nMatch {match_id} - {poll_type} Results:")
        print(f"Correct option: {correct_option}")
        print(f"Number of eligible users: {len(votes)}")
        print(f"Number of winners: {len(winners)}")
        print(f"Number of losers (including no votes): {len(losers)}")
        print(f"Winners: {winners}")
        print(f"Losers: {losers}")
    
    # Print final standings for this processing session
    if total_points:
        print("\nPoints awarded in this session:")
        for user_id, points in sorted(total_points.items(), key=lambda x: x[1], reverse=True):
            print(f"User {user_id}: {points} points")

if __name__ == "__main__":
    main() 