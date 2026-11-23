# Problem Statement

## AI-Powered Restaurant Recommendation System (Zomato Use Case)

Build an AI-powered restaurant recommendation service inspired by Zomato. The system suggests restaurants from a real restaurant dataset by combining structured filtering with a large language model (LLM), so recommendations match the user’s stated preferences and are explained in plain language.

## Objective

Design and implement an application that:

- Takes user preferences such as location, budget, cuisine, and ratings.
- Uses a real-world dataset of restaurants.
- Uses an LLM to generate personalized, human-like recommendations.
- Displays clear and useful results to the user.

## System Workflow

### 1. Data ingestion

- Load and preprocess the Zomato dataset from Hugging Face: [ManikaSaini/zomato-restaurant-recommendation](https://huggingface.co/datasets/ManikaSaini/zomato-restaurant-recommendation).
- Extract relevant fields such as restaurant name, location, cuisine, cost, and rating.

### 2. User input

Collect:

- **Location** — for example, Bangalore.
- **Budget** — low, medium, or high.
- **Cuisine** — for example, Italian or Chinese.
- **Minimum rating**.
- **Additional preferences** — for example, family-friendly or quick service.

### 3. Integration layer

- Filter and prepare the relevant restaurant records from the user’s input.
- Pass those structured results into an LLM prompt.
- Design the prompt so the model can reason about the options and rank them.

### 4. Recommendation engine

Use the LLM to:

- Rank restaurants.
- Explain why each recommendation fits the user’s preferences.
- Optionally summarize the choices.

### 5. Output display

Present the top recommendations in a user-friendly format. Each result includes:

- Restaurant name
- Cuisine
- Rating
- Estimated cost
- AI-generated explanation

## Context for the project

This document is the source of truth for what the project must do.

| Area | Requirement |
| --- | --- |
| Domain | Restaurant discovery and recommendation, in the style of Zomato |
| Data | Hugging Face dataset `ManikaSaini/zomato-restaurant-recommendation`, preprocessed down to name, location, cuisine, cost, rating, and related fields |
| User preferences | Location, budget (low / medium / high), cuisine, minimum rating, and free-form extras |
| Retrieval | Filter the dataset from those preferences before calling the model |
| Model role | Rank the filtered set, explain each pick, and optionally summarize |
| Presentation | Top recommendations with name, cuisine, rating, estimated cost, and the model’s explanation |

The application succeeds when a user can enter preferences, the system narrows the dataset to matching restaurants, the LLM ranks and explains those matches, and the UI shows the top results in the format above.
