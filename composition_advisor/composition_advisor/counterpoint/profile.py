"""The versioned educational policy, not a claim to reproduce Fux verbatim."""

from copy import deepcopy

PROFILE_ID = "fux_inspired_two_voice_v1"
PROFILE_VERSION = "1"
ENGINE_VERSION = "1.0.0"

_RULES = [
    ("input_format", "入力形式", "error", "1小節に全音符1音。整数tick・一意で固定の音符ID・正しい声部・指定プロファイルを必須とします。"),
    ("cantus_integrity", "定旋律の保護", "error", "定旋律の音高・綴り・位置・長さ・IDを原本と照合します。"),
    ("missing_note", "未入力", "error", "各小節に対旋律を1音入力してください。未完成の回答は合格しません。"),
    ("pitch_range", "指定音域", "error", "対旋律は課題に表示した音域内に収めます。"),
    ("diatonic_pitch", "調と音名の綴り", "error", "初期課題は長調（Ionian）のみ。調号どおりの7音を使い、異名同音の置換や追加の臨時記号は用いません。"),
    ("vertical_consonance", "垂直音程の協和", "error", "完全同度・5度・8度、長短3度・6度とその複音程を許容。完全4度、増減音程などは不協和です。"),
    ("interior_unison", "途中の同度", "error", "実音の同度は開始と終止に限ります。途中のオクターブは許容します。"),
    ("voice_crossing", "声部交差", "error", "同じ小節で、指定された上声と下声の高さが逆転してはいけません。"),
    ("voice_overlap", "声部の重なり", "error", "上声が直前の下声より低く、または下声が直前の上声より高く進むことを禁止します。同じ高さへの到達は許容します。"),
    ("parallel_fifth", "連続完全5度", "error", "両声が同方向に動き、完全5度系（12度などを含む）が続くことを禁止します。反行・斜行はこの規則の対象外です。"),
    ("parallel_octave", "連続完全8度・同度", "error", "両声が同方向に動き、完全同度・8度・15度等の同じ音程族が続くことを禁止します。反行・斜行はこの規則の対象外です。"),
    ("contrary_perfect", "反行による完全音程の連続", "warning", "反行で同じ完全5度系、または同度・8度系が続くときに警告します。参照教材の厳格な種対位法では禁則ですが、この学習プロファイルでは警告に留めます。"),
    ("direct_perfect", "直接進行", "error", "同方向に完全5度・8度系へ到達し、上声が3度以上跳躍した場合に指摘します。上声の順次進行は許容。連続完全音程と二重計上しません。"),
    ("direct_step_perfect", "上声の順次進行による直接進行", "warning", "同方向に完全5度・8度系へ到達しても、上声が順次進行なら警告に留めます。参照教材の厳格な種対位法との意図的な相違点です。"),
    ("opening", "開始", "error", "上声の対旋律は実音の完全同度・5度・8度、下声の対旋律は完全同度・8度で始めます。"),
    ("ending", "終止音", "error", "両声とも主音で終え、最後の垂直音程は実音の完全同度または8度にします。"),
    ("cadence", "長調の終止形", "error", "両声の反行・順次進行で終止します。一方が導音から主音へ半音上行し、もう一方が第2音から主音へ全音下行します。"),
    ("melodic_interval", "旋律音程", "error", "順次進行、長短3度、完全4度・5度・8度、上行の短6度を許容。増減音程、7度、長6度、下行短6度、8度を超す跳躍は禁止します。"),
    ("leap_recovery", "跳躍後の処理", "warning", "4度以上の跳躍の後は、逆向きの順次進行を勧めます。これは合否を左右しない学習上の推奨です。"),
    ("successive_leaps", "連続する跳躍", "warning", "同方向の跳躍が2回続くとき、歌いやすい輪郭か確認します。"),
    ("repeated_pitch", "同音反復", "warning", "対旋律で隣り合う同音を避けることを勧めます。斜行そのものは禁止しません。"),
    ("melodic_range", "旋律の音域", "warning", "対旋律の全体の幅は10度以内を勧めます。課題の指定音域とは別の推奨です。"),
    ("climax", "最高音", "warning", "対旋律の最高音を一度だけ用いることを勧めます。唯一の正解や音楽的品質の判定ではありません。"),
    ("voice_spacing", "声部間隔", "warning", "声部間が10度を超えるとき、まとまりを聴いて確認します。複音程そのものは禁止しません。"),
]

_PROFILE = {
    "id": PROFILE_ID, "version": PROFILE_VERSION,
    "title": "フックスを参考にした2声・第1種（長調）",
    "description": "公開教材を参考に範囲を定めた独自の学習用規則です。原典の完全再現や音楽としての優劣の採点ではありません。全音符1対1、4/4、長調のみ。警告は合否に影響しません。",
    "rules": [{"id": r[0], "title": r[1], "severity": r[2], "description": r[3]} for r in _RULES],
    "sources": [
        {"title": "Open Music Theory — First-Species Counterpoint", "url": "https://viva.pressbooks.pub/openmusictheorycopy/chapter/first-species-counterpoint/"},
        {"title": "Music Theory for the 21st-Century Classroom — First Species", "url": "https://musictheory.pugetsound.edu/mt21c/FirstSpecies.html"},
        {"title": "Open Music Theory — Cantus Firmus", "url": "https://openmusictheory.github.io/cantusFirmus.html"},
        {"title": "music21 — Interval", "url": "https://www.music21.org/music21docs/moduleReference/moduleInterval.html"},
    ],
}

RULE_BY_ID = {r["id"]: r for r in _PROFILE["rules"]}


MULTI_SPECIES_VERSION = "2"
MULTI_SPECIES_ENGINE_VERSION = "2.0.0"

_PROFILE_V2 = deepcopy(_PROFILE)
_PROFILE_V2.update(
    version=MULTI_SPECIES_VERSION,
    title="2声・第2〜5種（長調・固定リズム）",
    description="長調の固定リズム課題です。第2種は弱拍の経過音、第3種は弱拍の経過音と第2・4拍の刺繍音、第4種は準備・保持・下行解決する掛留、第5種はこれらを混ぜた指定リズムを扱います。自由なリズム作成、カンビアータ、二重刺繍、8分音符、装飾された掛留の解決は対象外です。完全音程への直接進行と反行の扱いは第1種v1の学習方針を引き継ぎます。警告は合否に影響しません。",
)
_V2_OVERRIDES = {
    "input_format": "課題のnoteSlotsに指定した開始tick・長さ・一意の音符ID・声部・プロファイルを必須とします。小節を跨ぐ保持音は1つの長い音符で表します。",
    "missing_note": "指定された全ての音符枠を入力してください。休符は課題側で固定し、未入力とは区別します。",
    "vertical_consonance": "協和は完全同度・5度・8度、長短3度・6度とその複音程です。不協和は種・拍に応じて規定した経過音・刺繍音・掛留だけを許容します。",
    "voice_crossing": "どの同時発音区間でも、指定された上声と下声の高さを逆転させません。",
    "parallel_fifth": "隣接する同時発音区間と連続する強拍の完全5度系を比較します。第4・5種では連続する第3拍も比較し、保持音で隠れる連続完全5度を確認します。両声が同方向に動く場合を禁止します。",
    "parallel_octave": "隣接する同時発音区間と連続する強拍の同度・8度系を比較します。第4・5種では連続する第3拍も比較します。両声が同方向に動く場合を禁止します。",
    "cadence": "最後の対旋律の新しい音から終止音へ順次進行し、定旋律の最後の進行と合わせて導音の半音上行・第2音の全音下行の反行終止を作ります。第4種の上声課題は、最後から2小節目の強拍へ主音を保持し、第3拍で導音に下行解決して主音へ戻る7–6の終止を必須とします。",
}
for _rule in _PROFILE_V2["rules"]:
    if _rule["id"] in _V2_OVERRIDES:
        _rule["description"] = _V2_OVERRIDES[_rule["id"]]
_PROFILE_V2["rules"].extend([
    {"id": "strong_consonance", "title": "強拍の協和", "severity": "error", "description": "第2・3種では小節の第1拍を必ず協和にします。第4・5種の第1拍での不協和は、前の弱拍から保持した適正な掛留に限ります。"},
    {"id": "weak_dissonance", "title": "弱拍の不協和音", "severity": "error", "description": "第2種の第3拍は協和音に挟まれた同方向・順次進行の経過音のみ。第3・5種は弱拍の経過音、および第2・4拍で元の音へ戻る順次進行の刺繍音を許容します。前後の音は協和である必要があります。"},
    {"id": "suspension_preparation", "title": "掛留の準備", "severity": "error", "description": "掛留音は直前の小節の第3拍から同一の音符で保持し、準備の時点で協和にします。タイを音高の違う音へ結ぶことはできません。"},
    {"id": "suspension_resolution", "title": "掛留の解決", "severity": "error", "description": "強拍の不協和な保持音は、その小節の第3拍で下行順次進行し協和に解決します。上声は7–6、4–3、9–8（複音程可）、下声は2–3（複音程可）を扱います。"},
])
_PROFILE_V2["sources"].extend([
    {"title": "Open Music Theory — Second-Species Counterpoint", "url": "https://openmusictheory.github.io/secondSpecies.html"},
    {"title": "Open Music Theory — Third-Species Counterpoint", "url": "https://openmusictheory.github.io/thirdSpecies.html"},
    {"title": "Open Music Theory — Fourth-Species Counterpoint", "url": "https://viva.pressbooks.pub/openmusictheorycopy/chapter/fourth-species-counterpoint/"},
    {"title": "Open Music Theory — Fifth-Species Counterpoint", "url": "https://viva.pressbooks.pub/openmusictheorycopy/chapter/fifth-species-counterpoint/"},
])
V2_RULE_BY_ID = {r["id"]: r for r in _PROFILE_V2["rules"]}


def profile(version: str | None = None) -> dict:
    if version == PROFILE_VERSION:
        return deepcopy(_PROFILE)
    if version in {None, MULTI_SPECIES_VERSION}:
        return deepcopy(_PROFILE_V2)
    raise KeyError(version)
