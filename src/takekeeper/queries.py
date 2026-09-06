from __future__ import annotations

from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class EditorialConstraints:
    production_id: str
    scene_id: str
    min_rating: int
    target_line_present: bool = True
    eyeline: str = "toward_door"
    boom_visible: bool = False

def _sql_string(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"

def continuity_evidence_sql(production_id: str, scene_id: str, take_id: str) -> str:
    return f"""WITH {_sql_string(production_id)} AS p, {_sql_string(scene_id)} AS s, {_sql_string(take_id)} AS t
SELECT o.entity_id, o.property_key, o.normalized_value AS observed_value, o.confidence,
       o.evidence_start_ms, o.evidence_end_ms, b.baseline_value,
       b.source_take_id AS baseline_source_take_id
FROM takekeeper.observations AS o
LEFT JOIN takekeeper.continuity_baselines AS b
  ON b.production_id=o.production_id AND b.scene_id=o.scene_id
 AND b.entity_id=o.entity_id AND b.property_key=o.property_key AND b.active=true
WHERE o.production_id=p AND o.scene_id=s AND o.take_id=t
ORDER BY o.entity_id, o.property_key"""

def editorial_retrieval_sql(c: EditorialConstraints) -> str:
    boom = "true" if c.boom_visible else "false"
    line_present = "true" if c.target_line_present else "false"
    return f"""SELECT t.take_id, t.take_number, t.director_rating,
 maxIf(o.evidence_start_ms, o.property_key='dialogue.target_line_present') AS dialogue_evidence_ms,
 maxIf(o.evidence_start_ms, o.property_key='performance.eyeline.after_target_line') AS eyeline_evidence_ms
FROM takekeeper.takes AS t
INNER JOIN takekeeper.observations AS o
 ON o.production_id=t.production_id AND o.scene_id=t.scene_id AND o.take_id=t.take_id
WHERE t.production_id={_sql_string(c.production_id)} AND t.scene_id={_sql_string(c.scene_id)}
 AND t.director_rating >= {int(c.min_rating)}
GROUP BY t.take_id, t.take_number, t.director_rating
HAVING countIf(o.property_key='dialogue.target_line_present' AND o.normalized_value={_sql_string(line_present)}) > 0
 AND countIf(o.property_key='performance.eyeline.after_target_line' AND o.normalized_value={_sql_string(c.eyeline)}) > 0
 AND countIf(o.property_key='quality.boom_visible' AND o.normalized_value={_sql_string(boom)}) > 0
ORDER BY t.director_rating DESC, t.take_number ASC"""
