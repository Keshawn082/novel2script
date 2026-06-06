"""
POC 验证：instructor 整集生成 EpisodeScript 的可行性

使用方法：
  1. 复制 .env.example 为 .env，填入 API Key
  2. 运行：python tests/poc_instructor_episode.py

验证点：
  1. instructor 能否完整输出嵌套的 EpisodeScript（不被截断）
  2. 嵌套字段（scenes→shots→dialogues）是否完整
  3. 枚举值是否被正确约束（景别、机位、画面位置等）
  4. 最大 token 消耗是多少
  5. YAML round-trip：model → YAML → 解析 → 一致性

如果 POC 失败（截断/字段缺失/校验不通过），则需改为逐场景生成方案。
"""
import os
import sys
import json
import asyncio
from pathlib import Path

# 添加项目根目录到 path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from pydantic import BaseModel, Field, ValidationError
from typing import Optional, List
from enum import Enum
from openai import AsyncOpenAI


# ── 从 yaml_schema 复制模型定义（POC 阶段直接内联，后续从 app.core.yaml_schema 导入）──

class ShotSize(str, Enum):
    EXTREME_LONG = "大远景"
    LONG = "远景"
    FULL = "全景"
    MEDIUM = "中景"
    CLOSE = "近景"
    CLOSE_UP = "特写"
    EXTREME_CLOSE_UP = "大特写"

class CameraAngle(str, Enum):
    LEVEL = "平拍"
    HIGH = "俯拍"
    LOW = "仰拍"
    SIDE = "侧拍"

class FramePosition(str, Enum):
    CENTER = "画中"
    LEFT = "画左"
    RIGHT = "画右"

class ShotType(str, Enum):
    REGULAR = "regular"
    CLOSE_UP = "close_up"
    SUBJECTIVE = "subjective"
    INSERT = "insert"
    CUT = "cut"
    FLASHBACK = "flashback"

class TimeOfDay(str, Enum):
    DAY = "日"
    NIGHT = "夜"
    DUSK = "黄昏"
    DAWN = "清晨"

class LocationType(str, Enum):
    INTERIOR = "内"
    EXTERIOR = "外"

class StoryPhase(str, Enum):
    HOOK = "开篇钩子期"
    FIRST_CRISIS = "第一转折点/危机"
    FIRST_CLIMAX = "第一个小高潮"
    MIDPOINT = "中点反转"
    DARKEST = "至暗时刻"
    FINAL_BATTLE = "终极反击/高潮"
    ENDING = "结局"

class Voiceover(BaseModel):
    character: str
    content: str = Field(..., max_length=30)

class Dialogue(BaseModel):
    character: str
    emotion: Optional[str] = None
    line: str = Field(..., max_length=20)

class SoundEffect(BaseModel):
    moment: str
    sound: str
    position: Optional[str] = None

class BGMChange(BaseModel):
    moment: str
    bgm: str

class Shot(BaseModel):
    shot_size: Optional[ShotSize] = None
    camera_angle: Optional[CameraAngle] = None
    frame_position: Optional[FramePosition] = None
    description: str = Field(..., min_length=5)
    type: ShotType = ShotType.REGULAR
    characters: List[str] = []
    content: Optional[str] = None
    end: Optional[bool] = None
    props: List[str] = []

class Scene(BaseModel):
    id: str = Field(..., pattern=r"^\d+-\d+$")
    time: TimeOfDay
    location_type: LocationType
    location: str
    ambience: str
    bgm: str
    characters: List[str] = Field(..., min_length=1)
    voiceover: Optional[Voiceover] = None
    markers: List[str] = []
    shots: List[Shot] = Field(..., min_length=1)
    sound_effects: List[SoundEffect] = []
    dialogues: List[Dialogue] = []
    bgm_changes: List[BGMChange] = []
    transitions: List[str] = []
    props: List[str] = []
    subtitles: List[str] = []

class EpisodeScript(BaseModel):
    episode_number: int = Field(..., ge=1)
    title: str = Field(..., min_length=1, max_length=100)
    phase: StoryPhase
    emotional_curve: str = Field(..., min_length=5)
    scenes: List[Scene] = Field(..., min_length=1)
    episode_ending: str = Field(..., min_length=20)
    next_episode_hook: str = Field(..., min_length=10)


# ── 测试用例 ──

SAMPLE_OUTLINE = """
第1集：暗流

本集大纲：
苏瑶是苏家染坊的女主人，以一手出神入化的靛蓝染技闻名古镇。一日，她的得力助手林羽急匆匆赶来，告知镇上的布庄全部拒收染坊的货，理由是"染料有问题，会掉色"。
苏瑶拿起退单看了一眼，先是微拧眉头，随即恢复异常的平静。她走到成品布匹旁，扯下一块浸入水中搓洗——水清澈见底，没有丝毫掉色。苏瑶平静地说："布没问题。是有人在背后打了招呼。"
林羽压低声音问出苏琴的名字。苏瑶没有回答，望向街对面新开的"琴记绸缎"——那是她姐姐苏琴的店。
夜深了，苏瑶独自坐在染坊后巷的石阶上。三年前，姐姐苏琴夺走了她的婚约，穿着大红嫁衣嫁给了她爱的人。如今苏琴又暗中打压她的生意。苏瑶攥紧退单，指节发白。
她深吸一口气，将退单缓缓撕成碎片。月光从云层透出，照亮她冷峻的侧脸。某种决定在她心中成形——她不会再退让了。
"""

SAMPLE_CHARACTERS = """
【核心角色】
苏瑶：女，28岁，苏家染坊女主人。性格坚韧隐忍，外柔内刚。靛蓝色粗布短褂，袖口挽到小臂，发髻用木簪别着。五官精致但常带疲惫，眼神锐利。
林羽：男，30岁，染坊大徒弟。忠厚老实，对苏瑶忠心耿耿。身材魁梧，穿灰色短褐，手指因常年接触染料而靛蓝。
苏琴：女，30岁，苏瑶的姐姐。野心勃勃，三年前夺走妹妹的婚约。嫁入豪门后开绸缎庄。衣着华丽，妆容精致，眼神中带着算计。
"""

SAMPLE_PREV_ENDING = None  # 第1集无上集


# ── 提示词模板 ──

SYSTEM_PROMPT_TEMPLATE = """你是一位专精竖屏短剧的资深编剧，擅长将剧情大纲扩写为详细的分集剧本。

【剧本参数】
* 每集时长：{duration} 分钟
* 每集场景上限：{max_scenes} 个
* 台词占比：{dialogue_ratio}%
* 题材类型：{genres}
* 受众定位：{gender}
* 叙事阶段：{phase}

【输出要求】
根据提供的大纲和角色信息，输出完整的剧集剧本。注意：
- 每句台词不超过20字
- 每个场景至少包含1个环境音+1个BGM+2-3个音效
- 镜头角度至少使用3种以上（平拍/俯拍/仰拍/侧拍）
- 场景编号格式：{episode_number}-场次
- 角色首次出场时描写外貌状态
- 每个场景的角色情绪必须有层次递进"""


async def run_poc():
    # ── 配置 ──
    api_key = os.getenv("POC_API_KEY", "")
    base_url = os.getenv("POC_BASE_URL", "https://api.deepseek.com")
    model = os.getenv("POC_MODEL", "deepseek-chat")

    if not api_key:
        print("=" * 60)
        print("❌ 请在 .env 文件中设置 POC_API_KEY")
        print("=" * 60)
        print("\n.env 示例：")
        print("POC_API_KEY=sk-xxxx")
        print("POC_BASE_URL=https://api.deepseek.com")
        print("POC_MODEL=deepseek-chat")
        return False

    print("=" * 60)
    print("POC: instructor 整集生成 EpisodeScript 验证")
    print("=" * 60)
    print(f"  API Base: {base_url}")
    print(f"  Model: {model}")
    print()

    client = AsyncOpenAI(api_key=api_key, base_url=base_url)

    # ── 尝试导入 instructor ──
    try:
        from instructor import from_openai
        instructor_client = from_openai(client)
        print("✓ instructor 导入成功")
    except ImportError:
        print("❌ instructor 未安装，请运行: pip install instructor")
        return False

    # ── 构建消息 ──
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
        duration=2,
        max_scenes=5,
        dialogue_ratio=40,
        genres="古言, 商战, 女性成长",
        gender="女频",
        phase="开篇钩子期",
        episode_number=1,
    )

    user_prompt = f"""【角色信息】
{SAMPLE_CHARACTERS}

【本集信息】
第1集 / 共80集
标题：暗流
叙事阶段：开篇钩子期

【本集大纲】
{SAMPLE_OUTLINE}

请根据以上信息，生成第1集的完整剧本。"""

    # ── 执行 ──
    print("正在调用 instructor (response_model=EpisodeScript)...")
    print(f"  System prompt 长度: {len(system_prompt)} 字符")
    print(f"  User prompt 长度: {len(user_prompt)} 字符")
    print()

    try:
        print("⏳ 等待 AI 响应（可能需要 30-120 秒）...")
        script: EpisodeScript = await instructor_client.chat.completions.create(
            model=model,
            response_model=EpisodeScript,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=8192,
            temperature=0.3,
        )
        print("✓ instructor 调用成功")
    except Exception as e:
        print(f"❌ instructor 调用失败: {e}")
        return False

    # ── 验证 ──
    print()
    print("─" * 40)
    print("验证结果")
    print("─" * 40)

    checks = []

    # 1. 顶层字段
    checks.append(("episode_number", script.episode_number == 1, f"值={script.episode_number}"))
    checks.append(("title 非空", len(script.title) > 0, f"'{script.title}'"))
    checks.append(("phase", script.phase == StoryPhase.HOOK, f"{script.phase.value}"))
    checks.append(("emotional_curve 非空", len(script.emotional_curve) >= 5, script.emotional_curve[:50]))
    checks.append(("scenes 数量", len(script.scenes) >= 1, f"共 {len(script.scenes)} 个场景"))
    checks.append(("episode_ending", len(script.episode_ending) >= 20, f"{len(script.episode_ending)} 字"))
    checks.append(("next_episode_hook", len(script.next_episode_hook) >= 10, f"{len(script.next_episode_hook)} 字"))

    all_ok = True
    for name, ok, detail in checks:
        status = "✓" if ok else "❌"
        if not ok:
            all_ok = False
        print(f"  {status} {name}: {detail}")

    # 2. 场景级别验证
    for scene in script.scenes:
        scene_ok = True
        if len(scene.shots) == 0:
            print(f"  ❌ 场景 {scene.id}: shots 为空")
            all_ok = False
            scene_ok = False
        if len(scene.characters) == 0:
            print(f"  ❌ 场景 {scene.id}: characters 为空")
            all_ok = False
            scene_ok = False

        # 验证场景 ID 格式
        import re
        if not re.match(r"^\d+-\d+$", scene.id):
            print(f"  ❌ 场景 ID 格式错误: {scene.id}")
            all_ok = False
            scene_ok = False

        # 统计 scene 内部数据
        shot_count = len(scene.shots)
        dialogue_count = len(scene.dialogues)
        sfx_count = len(scene.sound_effects)

        # 检查镜头是否有枚举值（regular 类型应有）
        regular_shots = [s for s in scene.shots if s.type == ShotType.REGULAR]
        bad_shots = [s for s in regular_shots if not (s.shot_size and s.camera_angle and s.frame_position)]
        if bad_shots:
            print(f"  ⚠ 场景 {scene.id}: {len(bad_shots)} 个 regular 镜头缺少景别/机位/画面位置")

        if scene_ok:
            print(f"  ✓ 场景 {scene.id}: {shot_count} 镜头, {dialogue_count} 对白, {sfx_count} 音效, "
                  f"{len(scene.bgm_changes)} BGM变化")

    # 3. 枚举值正确性验证
    enum_errors = []
    for scene in script.scenes:
        for shot in scene.shots:
            if shot.shot_size and shot.shot_size not in ShotSize:
                enum_errors.append(f"场景 {scene.id}: 非法景别 {shot.shot_size}")
            if shot.camera_angle and shot.camera_angle not in CameraAngle:
                enum_errors.append(f"场景 {scene.id}: 非法机位 {shot.camera_angle}")
        if scene.time not in TimeOfDay:
            enum_errors.append(f"场景 {scene.id}: 非法时间 {scene.time}")

    if enum_errors:
        print(f"\n  ❌ 枚举值错误 ({len(enum_errors)} 个):")
        for err in enum_errors[:5]:
            print(f"    - {err}")
        all_ok = False
    else:
        print(f"\n  ✓ 所有枚举值正确")

    # 4. 对白字数验证
    long_lines = []
    for scene in script.scenes:
        for d in scene.dialogues:
            if len(d.line) > 20:
                long_lines.append(f"场景 {scene.id}, {d.character}: '{d.line}' ({len(d.line)}字)")

    if long_lines:
        print(f"  ⚠ 台词超20字 ({len(long_lines)} 处，instructor 模式下 max_length 硬约束通常生效)")
        for ll in long_lines[:3]:
            print(f"    - {ll}")
    else:
        print(f"  ✓ 所有台词 ≤20字")

    # 5. YAML round-trip
    try:
        yaml_text = script.to_yaml()
        parsed = EpisodeScript.from_yaml(yaml_text)

        # 比较关键字段
        if (parsed.episode_number == script.episode_number and
            parsed.title == script.title and
            len(parsed.scenes) == len(script.scenes)):
            print(f"  ✓ YAML round-trip 成功 (YAML 共 {len(yaml_text)} 字符)")
        else:
            print(f"  ❌ YAML round-trip 数据不一致")
            all_ok = False
    except Exception as e:
        print(f"  ❌ YAML round-trip 失败: {e}")
        all_ok = False

    # ── 保存 YAML 样本 ──
    yaml_path = Path(__file__).parent / "poc_output_sample.yaml"
    yaml_text = script.to_yaml()
    yaml_path.write_text(yaml_text, encoding="utf-8")
    print(f"\n  📄 YAML 样本已保存到: {yaml_path}")

    # ── 总结 ──
    print()
    print("=" * 60)
    if all_ok and not long_lines:
        print("✅ POC 通过：instructor 可以整集生成完整的 EpisodeScript")
        print("   建议继续使用整集生成方案。")
    elif all_ok:
        print("⚠️ POC 基本通过：存在台词超长警告，但 instructor 硬约束拦截成功")
        print("   建议继续使用整集生成方案，需关注 max_length 是否真正生效。")
    else:
        print("❌ POC 未通过：存在字段缺失或校验失败")
        print("   建议改为逐场景生成方案，或调整 EpisodeScript 的字段约束。")
    print("=" * 60)

    return all_ok


if __name__ == "__main__":
    asyncio.run(run_poc())
