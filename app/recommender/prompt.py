"""Prompt for ranking a filtered restaurant short list."""

from __future__ import annotations

from collections.abc import Sequence

from app.catalog.models import Preferences, Restaurant
from app.config import ALL_BANGALORE


def build_messages(
    preferences: Preferences,
    candidates: Sequence[Restaurant],
) -> list[dict[str, str]]:
    """Return a system message and a user message for one ranking call.

    Only catalog fields are included. Phone numbers and menus are omitted,
    and a missing cost or rating is left out instead of filled with a number.
    """
    system = (
        "Reply with a JSON object only. "
        'The object has "summary" and "recommendations". '
        'Each recommendation has "id", "rank", and "explanation". '
        "Every id comes from the candidate list. "
        f"The number of recommendations is at most {preferences.limit}. "
        "Explanations use the extra wishes, rest type, dishes, booking flags, and review snippets. "
        "The summary is one short paragraph."
    )
    blocks = [_candidate_block(candidate) for candidate in candidates]
    user = _preference_text(preferences) + "\n\n" + "\n\n".join(blocks)
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def _preference_text(preferences: Preferences) -> str:
    if preferences.location.casefold() == ALL_BANGALORE.casefold():
        lines = ["The person is looking across all of Bangalore."]
    else:
        lines = [f"The person is looking in {preferences.location}."]
    if preferences.budget is not None:
        lines.append(f"The budget is {preferences.budget}.")
    if preferences.cuisine is not None:
        lines.append(f"The cuisine should match {preferences.cuisine}.")
    if preferences.min_rating is not None:
        lines.append(f"The minimum rating is {preferences.min_rating}.")
    if preferences.preferences is not None:
        lines.append(f"Extra wishes: {preferences.preferences}")
    return "\n".join(lines)


def _candidate_block(restaurant: Restaurant) -> str:
    lines = [
        f"id: {restaurant.id}",
        f"name: {restaurant.name}",
        f"neighborhood: {restaurant.location}",
    ]
    if restaurant.cuisines:
        lines.append("cuisines: " + ", ".join(restaurant.cuisines))
    if restaurant.rest_types:
        lines.append("rest types: " + ", ".join(restaurant.rest_types))
    if restaurant.dishes_liked:
        lines.append("liked dishes: " + ", ".join(restaurant.dishes_liked))
    if restaurant.cost_for_two is not None:
        lines.append(f"cost for two: {restaurant.cost_for_two}")
    if restaurant.rating is not None:
        lines.append(f"rating: {restaurant.rating}")
    lines.append(f"votes: {restaurant.votes}")
    lines.append("online order: " + ("yes" if restaurant.online_order else "no"))
    lines.append("table booking: " + ("yes" if restaurant.book_table else "no"))
    for snippet in restaurant.review_snippets[:2]:
        lines.append(f"review: {snippet}")
    return "\n".join(lines)
