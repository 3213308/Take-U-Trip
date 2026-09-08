# app/evaluation/dataset.py
"""评估数据集 — Golden Cases

每个用例定义：
- input: 用户输入
- expected_tools: 期望至少调用的工具（召回）
- forbidden_tools: 不应调用的工具（误调用）
- expected_args: 关键参数期望
- max_iterations: 合理步数上限
- check_points: 最终结果必须满足的约束
"""

from dataclasses import dataclass, field


@dataclass
class EvalCase:
    case_id: str
    input: str
    user_id: str = "eval-user"
    expect_itinerary: bool = True
    expected_tools: list[str] = field(default_factory=list)
    forbidden_tools: list[str] = field(default_factory=list)
    expected_args: dict = field(default_factory=dict)   # {"get_weather": {"city": "成都"}}
    max_iterations: int = 6
    check_points: list[str] = field(default_factory=list)  # LLM Judge 检查点


EVAL_CASES: list[EvalCase] = [
    EvalCase(
        case_id="case_001_basic_weather_attraction",
        input="成都今天天气怎么样，有哪些历史古迹？",
        expect_itinerary=False,
        expected_tools=["get_weather", "search_attractions"],
        expected_args={
            "get_weather": {"city": "成都"},
            "search_attractions": {"city": "成都"},
        },
        max_iterations=3,
        check_points=["回答包含成都天气", "推荐了历史古迹类景点"],
    ),
    EvalCase(
        case_id="case_002_full_itinerary",
        input="帮我规划成都2日游，预算2000，喜欢历史古迹",
        expected_tools=["get_weather", "search_attractions", "search_hotels"],
        expected_args={"search_attractions": {"city": "成都"}},
        max_iterations=6,
        check_points=[
            "生成了2天的行程",
            "每天有多个活动且按时间排序",
            "历史古迹类景点占比高",
            "总预算不超过2000或明确说明超支",
        ],
    ),
    EvalCase(
        case_id="case_003_intercity_transport",
        input="我从北京去成都玩3天，怎么去比较好，预算3000",
        expected_tools=["search_transport", "search_hotels", "search_attractions"],
        expected_args={"search_transport": {"departure": "北京", "destination": "成都"}},
        max_iterations=6,
        check_points=["对比了高铁和飞机", "包含住宿安排", "生成3天行程"],
    ),
    EvalCase(
        case_id="case_004_food_focus",
        input="去成都玩，主要想吃火锅和小吃，推荐一下",
        expect_itinerary=False,
        expected_tools=["search_restaurants"],
        expected_args={"search_restaurants": {"city": "成都"}},
        max_iterations=4,
        check_points=["推荐了火锅", "推荐了小吃", "包含人均价格"],
    ),
    EvalCase(
        case_id="case_005_no_tool_needed",
        input="你好，你能做什么？",
        expect_itinerary=False,
        expected_tools=[],
        max_iterations=2,
        check_points=["介绍了自身能力", "没有强行规划行程"],
    ),
]
