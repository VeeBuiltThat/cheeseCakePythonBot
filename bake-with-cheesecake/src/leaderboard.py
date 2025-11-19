class Leaderboard:
    def __init__(self):
        self.scores = {}

    def add_score(self, player_name, score):
        if player_name in self.scores:
            self.scores[player_name] += score
        else:
            self.scores[player_name] = score

    def get_leaderboard(self):
        sorted_leaderboard = sorted(self.scores.items(), key=lambda item: item[1], reverse=True)
        return sorted_leaderboard

    def display_leaderboard(self):
        leaderboard = self.get_leaderboard()
        print("Leaderboard:")
        for rank, (player_name, score) in enumerate(leaderboard, start=1):
            print(f"{rank}. {player_name}: {score} points")