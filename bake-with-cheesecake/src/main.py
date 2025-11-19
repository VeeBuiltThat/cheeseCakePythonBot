import time
from user_interactions import greet_user, get_user_input
from leaderboard import Leaderboard
from commands.bake_pastries import bake_pastry
from commands.gather import gather
from commands.steal import steal
from commands.mix import mix
from commands.preheat import preheat
from commands.extinguish import extinguish
from commands.shoo import shoo
from commands.serve import serve
from commands.challenge import challenge

def main():
    leaderboard = Leaderboard()
    greet_user()
    
    while True:
        print("\nAvailable commands: $bake, $gather, $steal, $mix, $preheat, $extinguish, $shoo, $serve, $challenge, $exit")
        command = get_user_input("Enter a command: ")

        if command == "$exit":
            print("Thanks for playing! Goodbye!")
            break
        elif command == "$bake":
            bake_pastry()
        elif command == "$gather":
            gather()
        elif command == "$steal":
            steal()
        elif command == "$mix":
            mix()
        elif command == "$preheat":
            preheat()
        elif command == "$extinguish":
            extinguish()
        elif command == "$shoo":
            shoo()
        elif command == "$serve":
            serve()
        elif command == "$challenge":
            challenge()
        else:
            print("Invalid command. Please try again.")

        time.sleep(1)  # Adding a small delay for better user experience

if __name__ == "__main__":
    main()