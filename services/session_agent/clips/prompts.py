"""What Auntie Kemi says in each fixed prompt clip (PRD 4.1-4.4).

The web app shows this text in the speech bubble while the clip plays (session protocol
`clip_list`), and the prompt clips are synthesised from it, so the words heard and the
words shown are the same. Wording quoted in the PRD or the design-system README is used
as written; the rest follows the README's voice rules for children (sentences of eight
words or fewer, praise effort, at most one exclamation mark).
"""

PROMPT_TEXTS: dict[str, str] = {
    "interest_prompt": "Before we read, tell me: what kind of stories do you like?",  # PRD 4.1
    "interest_fallback": "Animals, football, space, food, or something else?",  # PRD 4.1
    "mic_check_prompt": "Let's count together. Say one, two, three, four, five.",
    "mic_closer": "Bring the phone a little closer. Count again.",  # PRD 4.1
    "mic_softer": "Speak a little softer. Count again.",  # PRD 4.1
    "story_almost_ready": "Your story is almost ready!",  # PRD 4.1
    "retell_prompt": "In your own words, tell me everything you remember from the story.",
    "anything_else": "Anything else?",  # PRD 4.1
    "take_your_time": "Take your time.",  # PRD 4.2
    "lets_go_next": "That's okay, let's go to the next one.",  # PRD 4.2
    "kind_end": "Thank you for reading to me! Now I will tell you a story.",
    "listening_retell_prompt": "Tell me my story in your own words.",
    "close_praise": "You did a great job today!",  # design-system README, "Session ends"
    "stop_praise": "We can stop now. Thank you for trying!",
    "wait_for_internet": "Let's wait for the internet.",  # PRD 4.4
}

WORD_CLIP_TEXT = "That word is {word}."  # PRD 4.1, 4.5 G5
