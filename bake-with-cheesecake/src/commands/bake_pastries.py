def bake_pastries():
    print("Welcome to the Bake with Cheesecake! Let's bake some pastries.")
    
    pastry_type = input("What type of pastry would you like to bake? (e.g., cheesecake, tart, pie): ")
    
    if pastry_type.lower() not in ['cheesecake', 'tart', 'pie']:
        print("Sorry, we don't have that pastry type. Please choose from cheesecake, tart, or pie.")
        return
    
    print(f"Great choice! You are baking a {pastry_type}.")
    
    ingredients = input("Please enter the ingredients you have (comma-separated): ")
    ingredients_list = [ingredient.strip() for ingredient in ingredients.split(',')]
    
    print("Let's check if you have the necessary ingredients...")
    
    required_ingredients = {
        'cheesecake': ['cream cheese', 'sugar', 'eggs', 'vanilla', 'crust'],
        'tart': ['flour', 'butter', 'sugar', 'fruit'],
        'pie': ['pie crust', 'filling', 'sugar', 'spices']
    }
    
    missing_ingredients = [ingredient for ingredient in required_ingredients[pastry_type] if ingredient not in ingredients_list]
    
    if missing_ingredients:
        print(f"You are missing the following ingredients for {pastry_type}: {', '.join(missing_ingredients)}")
        return
    
    print("You have all the ingredients! Let's start baking.")
    
    steps = {
        'cheesecake': [
            "Preheat the oven to 325°F (160°C).",
            "Mix cream cheese, sugar, and vanilla until smooth.",
            "Add eggs one at a time, mixing well.",
            "Pour into the crust and bake for 50-60 minutes.",
            "Let it cool and refrigerate before serving."
        ],
        'tart': [
            "Preheat the oven to 350°F (175°C).",
            "Mix flour, butter, and sugar to form the crust.",
            "Press the mixture into a tart pan.",
            "Fill with fruit and bake for 30-40 minutes.",
            "Let it cool before serving."
        ],
        'pie': [
            "Preheat the oven to 425°F (220°C).",
            "Prepare the pie crust and fill it with your choice of filling.",
            "Sprinkle sugar and spices on top.",
            "Bake for 45-50 minutes until golden brown.",
            "Let it cool before serving."
        ]
    }
    
    print("Here are the steps to bake your pastry:")
    for step in steps[pastry_type]:
        print(step)
    
    print("Happy baking!")