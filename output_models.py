from pydantic import BaseModel, Field

class AI_Agent_Vote(BaseModel):
    """vote of AI agent"""
    match_id: int = Field(description="id of the match")
    winner_selection: str = Field(description="winner team predicted by AI agent")
    margin_selection: str = Field(description="margin option choosen by AI agent")
    reasoning: str = Field(description="reasoning for the vote")