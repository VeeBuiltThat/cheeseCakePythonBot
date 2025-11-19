def get_user_input(prompt):
    return input(prompt)

def validate_input(user_input, valid_options):
    return user_input in valid_options

def display_message(message):
    print(message)

def prompt_for_baking_action():
    actions = ["bake", "gather", "steal", "mix", "preheat", "extinguish", "shoo", "serve", "challenge"]
    action = get_user_input(f"Choose an action from {actions}: ")
    while not validate_input(action, actions):
        display_message("Invalid action. Please try again.")
        action = get_user_input(f"Choose an action from {actions}: ")
    return action

def communicate_with_player(message):
    display_message(message)