# app/memory/context_builder.py
"""把用户画像和历史行程组装成 system prompt 片段"""


def build_memory_context(user_profile: dict, recent_itineraries: list[dict]) -> str:
    parts = []

    if user_profile:
        pref_lines = []
        if user_profile.get("dietary_restrictions"):
            pref_lines.append(f"- 饮食禁忌：{'、'.join(user_profile['dietary_restrictions'])}")
        if user_profile.get("attraction_preferences"):
            pref_lines.append(f"- 景点偏好：{'、'.join(user_profile['attraction_preferences'])}")
        if user_profile.get("avoid_categories"):
            pref_lines.append(f"- 避免：{'、'.join(user_profile['avoid_categories'])}")
        budget = user_profile.get("typical_budget_range", [])
        if budget and len(budget) == 2:
            pref_lines.append(f"- 通常预算：{budget[0]}-{budget[1]}元")
        if user_profile.get("travel_style"):
            pref_lines.append(f"- 出行风格：{user_profile['travel_style']}")
        if user_profile.get("transport_preference"):
            pref_lines.append(f"- 交通偏好：{user_profile['transport_preference']}")

        if pref_lines:
            parts.append("【用户长期偏好】\n" + "\n".join(pref_lines))

    if recent_itineraries:
        trip_lines = ["【最近行程】"]
        for trip in recent_itineraries[-3:]:
            it = trip.get("itinerary", {})
            trip_lines.append(
                f"- {it.get('destination', '未知')} {it.get('days', 0)}天 "
                f"预算{it.get('total_budget', 0):.0f}元"
            )
        parts.append("\n".join(trip_lines))

    return "\n\n".join(parts)
