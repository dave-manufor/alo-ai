"""What Auntie Kemi says in each fixed prompt clip (PRD 4.1-4.4).

The web app shows this text in the speech bubble while the clip plays (session protocol
`clip_list`), and the prompt clips are synthesised from it, so the words heard and the
words shown are the same. Wording quoted in the PRD is used as written; the rest is
drafted in the same voice and checked by the team before the clips are made.
"""

PROMPT_TEXTS: dict[str, str] = {
    "interest_prompt": "Before we read, tell me: what kind of stories do you like?",  # PRD 4.1
    "interest_fallback": "Animals, football, space, food, or something else?",  # PRD 4.1
    "mic_check_prompt": "Let's count together. Say one, two, three, four, five.",
    "mic_closer": "Bring the phone a little closer, then count again.",  # PRD 4.1
    "mic_softer": "Speak a little softer, then count again.",  # PRD 4.1
    "story_almost_ready": "Your story is almost ready!",  # PRD 4.1
    "retell_prompt": "In your own words, tell me everything you remember from the story.",
    "anything_else": "Anything else?",  # PRD 4.1
    "take_your_time": "Take your time.",  # PRD 4.2
    "lets_go_next": "That's okay, let's go to the next one.",  # PRD 4.2
    "kind_end": "Thank you for reading to me! Now I will tell you a story.",
    "listening_retell_prompt": "In your own words, tell me everything you remember from my story.",
    "close_praise": "Thank you! You did a great job today.",
    "stop_praise": "Thank you for reading with me today. Well done!",
    "wait_for_internet": "Let's wait for the internet.",  # PRD 4.4
}

WORD_CLIP_TEXT = "That word is {word}."  # PRD 4.1, 4.5 G5
