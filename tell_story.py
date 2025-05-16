from plugins_func.register import register_function, ToolType, ActionResponse, Action
from config.logger import setup_logging
import json
import asyncio

TAG = __name__
logger = setup_logging()

# Function description for storytelling
TELL_STORY_FUNCTION_DESC = {
    "type": "function",
    "function": {
        "name": "tell_story",
        "description": "Generate and narrate an engaging story based on user's preferences. This function is called when a user wants to hear a story or a novel.",
        "parameters": {
            "type": "object",
            "properties": {
                "theme": {
                    "type": "string",
                    "description": "The main theme or topic of the story (e.g., adventure, mystery, romance, friendship)"
                },
                "genre": {
                    "type": "string",
                    "description": "The genre of the story (e.g., fantasy, sci-fi, historical fiction, fairy tale)"
                },
                "length": {
                    "type": "string",
                    "description": "The desired length of the story (short, medium, long)"
                },
                "audience": {
                    "type": "string", 
                    "description": "The target audience (children, teens, adults)"
                },
                "continue_story": {
                    "type": "boolean",
                    "description": "Whether to continue a previously started story"
                }
            },
            "required": ["theme", "genre", "length", "audience"]
        }
    }
}

@register_function('tell_story', TELL_STORY_FUNCTION_DESC, ToolType.SYSTEM_CTL)
def tell_story(conn, theme="adventure", genre="fantasy", length="medium", audience="adults", continue_story=False):
    """
    Generate and tell a story to the user based on their preferences
    
    Args:
        conn: Connection object
        theme: Main theme or topic of the story
        genre: Genre of the story
        length: Desired length of the story (short, medium, long)
        audience: Target audience (children, teens, adults)
        continue_story: Whether to continue a previously started story
        
    Returns:
        ActionResponse: The LLM will generate and narrate the story
    """
    logger.bind(tag=TAG).info(f"Generating story: theme={theme}, genre={genre}, length={length}, audience={audience}, continue={continue_story}")
    
    # Define token/length constraints based on requested story length
    story_params = {
        "short": {
            "description": "a short story (about 500-700 words)",
            "sections": 2,
        },
        "medium": {
            "description": "a medium-length story (about 1000-1500 words)",
            "sections": 3,
        },
        "long": {
            "description": "a longer story (about 2000-2500 words)",
            "sections": 5,
        }
    }
    
    story_param = story_params.get(length.lower(), story_params["medium"])
    
    # Check if continuing a story
    if continue_story and hasattr(conn, 'current_story'):
        # If we have a story in progress, continue it
        current_story = conn.current_story
        logger.bind(tag=TAG).info(f"Continuing existing story with length {len(current_story)} characters")
        
        # Build prompt to continue the story
        prompt = f"""
        You're continuing a {genre} story for {audience} about {theme}.
        
        This is what has happened so far in the story:
        
        {current_story['summary']}
        
        The last part of the story ended with:
        
        {current_story['last_section']}
        
        Please write the next section of the story. Make this section engaging and well-paced for being read aloud.
        Create a natural continuation that builds on the existing characters and plot.
        Include dialogue and descriptive language to make the story engaging.
        
        IMPORTANT:
        1. Keep the tone, style, and characters consistent with the previous parts.
        2. Add new developments or challenges for the characters.
        3. Finish this section at a good stopping point, ideally with a bit of suspense to encourage the listener to want to hear more.
        4. Make the section approximately 800-1000 words.
        """
        
        # Submit the continuation request to LLM
        try:
            story_section = conn.llm.response_no_stream(
                system_prompt="You are a master storyteller creating engaging audio stories.",
                user_prompt=prompt
            )
            
            # Update the stored story
            conn.current_story['sections'].append(story_section)
            conn.current_story['last_section'] = story_section
            
            # Update the summary
            summary_prompt = f"""
            Here's the current summary of the story: 
            
            {conn.current_story['summary']}
            
            And here's the newest section of the story:
            
            {story_section}
            
            Please update the summary to include the new developments from this section.
            Keep the summary concise (about 200-300 words) but comprehensive.
            """
            
            updated_summary = conn.llm.response_no_stream(
                system_prompt="You are an expert at summarizing stories accurately and concisely.",
                user_prompt=summary_prompt
            )
            
            conn.current_story['summary'] = updated_summary
            
            # Check if we've reached the end
            conn.current_story['completed'] = "the end" in story_section.lower() or "the story ends" in story_section.lower()
            
            # Create the story title if we don't have one yet
            if 'title' not in conn.current_story or not conn.current_story['title']:
                title_prompt = f"""
                Based on the story so far, please create an engaging and appropriate title.
                The story is a {genre} story about {theme} for {audience}.
                
                Story summary: {updated_summary}
                
                Provide only the title, nothing else.
                """
                story_title = conn.llm.response_no_stream(
                    system_prompt="You create perfect, concise titles for stories.",
                    user_prompt=title_prompt
                )
                conn.current_story['title'] = story_title.strip()
            
            # Return the continuation to be read aloud
            title = conn.current_story['title']
            section_num = len(conn.current_story['sections'])
            
            # Prepare a message about the story continuation
            if conn.current_story['completed']:
                ending_message = "\n\nThat concludes the story. I hope you enjoyed it!"
            else:
                ending_message = "\n\nWould you like me to continue the story?"
                
            full_response = f"Continuing '{title}' - Part {section_num}:\n\n{story_section}{ending_message}"
            
            return ActionResponse(
                action=Action.REQLLM,
                result=full_response,
                response=None
            )
            
        except Exception as e:
            logger.bind(tag=TAG).error(f"Error continuing story: {str(e)}")
            return ActionResponse(
                action=Action.RESPONSE,
                result=f"Error continuing story: {str(e)}",
                response="I'm sorry, I had trouble continuing the story. Would you like me to try again or start a new story?"
            )
    else:
        # Starting a new story
        logger.bind(tag=TAG).info(f"Starting new {genre} story about {theme} for {audience}")
        
        # Build prompt for a new story
        prompt = f"""
        Create {story_param['description']} in the {genre} genre about {theme} appropriate for {audience}.
        
        The story should have:
        1. Engaging characters with clear personalities
        2. A well-structured plot with a beginning, middle, and end
        3. Appropriate pacing and language for the target audience
        4. Vivid descriptions and engaging dialogue
        
        IMPORTANT GUIDELINES FOR AUDIO STORYTELLING:
        1. Break the story into {story_param['sections']} distinct sections
        2. Use shorter paragraphs and sentences that are easy to follow when heard
        3. Include natural pauses and transitions between scenes
        4. If this is for children, use simpler vocabulary and more repetition
        5. Include dialogue with clear speaker attributions
        6. Avoid overly complex descriptions or too many characters
        7. Keep the emotional tone appropriate for {audience}
        
        Begin your story now. Write only the first section now (about 800-1000 words), ending at a natural point that makes the listener want to hear more.
        """
        
        # Submit the request to LLM
        try:
            # Generate the first section of the story
            first_section = conn.llm.response_no_stream(
                system_prompt="You are a master storyteller creating engaging audio stories.",
                user_prompt=prompt
            )
            
            # Generate a title for the story
            title_prompt = f"""
            Create a captivating title for a {genre} story about {theme} for {audience}.
            
            Here's the beginning of the story:
            
            {first_section[:500]}...
            
            Provide only the title, nothing else.
            """
            
            story_title = conn.llm.response_no_stream(
                system_prompt="You create perfect, concise titles for stories.",
                user_prompt=title_prompt
            )
            
            # Generate a summary of the first section
            summary_prompt = f"""
            Provide a concise summary (about 200 words) of this story section:
            
            {first_section}
            
            Focus on the main plot points, character introductions, and key developments.
            This summary will be used to maintain continuity when generating future sections.
            """
            
            section_summary = conn.llm.response_no_stream(
                system_prompt="You are an expert at summarizing stories accurately and concisely.",
                user_prompt=summary_prompt
            )
            
            # Store the story information for potential continuation
            conn.current_story = {
                'title': story_title.strip(),
                'theme': theme,
                'genre': genre,
                'audience': audience,
                'sections': [first_section],
                'last_section': first_section,
                'summary': section_summary,
                'completed': False
            }
            
            # Return the first section to be read aloud
            full_response = f"'{story_title.strip()}' - Part 1:\n\n{first_section}\n\nWould you like me to continue the story?"
            
            return ActionResponse(
                action=Action.REQLLM,
                result=full_response,
                response=None
            )
            
        except Exception as e:
            logger.bind(tag=TAG).error(f"Error generating story: {str(e)}")
            return ActionResponse(
                action=Action.RESPONSE,
                result=f"Error generating story: {str(e)}",
                response="I'm sorry, I had trouble creating a story. Would you like me to try again with a different theme?"
            )