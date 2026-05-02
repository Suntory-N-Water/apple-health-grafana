#!/usr/bin/env python3
"""
Apple Health export.xml を SQLite に変換するスクリプト
使い方: python3 parse_health.py <export.xml のパス> [db のパス]
"""

import sys
import sqlite3
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime

RECORD_TYPES = {
    "HKQuantityTypeIdentifierStepCount": "steps",
    "HKQuantityTypeIdentifierHeartRate": "heart_rate",
    "HKQuantityTypeIdentifierRestingHeartRate": "resting_heart_rate",
    "HKQuantityTypeIdentifierHeartRateVariabilitySDNN": "hrv",
    "HKQuantityTypeIdentifierActiveEnergyBurned": "active_energy",
    "HKQuantityTypeIdentifierAppleExerciseTime": "exercise_time",
    "HKQuantityTypeIdentifierDistanceWalkingRunning": "distance",
    "HKQuantityTypeIdentifierVO2Max": "vo2max",
    "HKQuantityTypeIdentifierRespiratoryRate": "respiratory_rate",
    "HKQuantityTypeIdentifierRunningSpeed": "running_speed",
    "HKQuantityTypeIdentifierOxygenSaturation": "oxygen_saturation",
}

SLEEP_STAGE_MAP = {
    "HKCategoryValueSleepAnalysisAsleepCore": "Core",
    "HKCategoryValueSleepAnalysisAsleepDeep": "Deep",
    "HKCategoryValueSleepAnalysisAsleepREM": "REM",
    "HKCategoryValueSleepAnalysisAsleepUnspecified": "Unspecified",
    "HKCategoryValueSleepAnalysisAwake": "Awake",
    "HKCategoryValueSleepAnalysisInBed": "InBed",
}

WORKOUT_TYPE_MAP = {
    "HKWorkoutActivityTypeWalking": "Walking",
    "HKWorkoutActivityTypeRunning": "Running",
    "HKWorkoutActivityTypeCycling": "Cycling",
    "HKWorkoutActivityTypeFunctionalStrengthTraining": "Strength",
}


def parse_date(s: str) -> str:
    try:
        return datetime.strptime(s[:19], "%Y-%m-%d %H:%M:%S").isoformat()
    except ValueError:
        return s[:19]


def create_tables(cur: sqlite3.Cursor):
    for table in RECORD_TYPES.values():
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {table} (
                time TEXT NOT NULL,
                value REAL,
                unit TEXT,
                source TEXT
            )
        """)
        cur.execute(f"DELETE FROM {table}")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS sleep (
            time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            stage TEXT NOT NULL,
            duration_min REAL NOT NULL,
            source TEXT
        )
    """)
    cur.execute("DELETE FROM sleep")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS workouts (
            time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            activity_type TEXT NOT NULL,
            duration_min REAL,
            distance_km REAL,
            energy_kcal REAL,
            source TEXT
        )
    """)
    cur.execute("DELETE FROM workouts")


def main(xml_path: str, db_path: str = "data/health.db"):
    print(f"パース中: {xml_path}")
    tree = ET.parse(xml_path)
    root = tree.getroot()

    con = sqlite3.connect(db_path)
    cur = con.cursor()
    create_tables(cur)

    counts: dict[str, int] = {}

    for elem in root:
        tag = elem.tag

        if tag == "Record":
            rtype = elem.attrib.get("type", "")

            if rtype == "HKCategoryTypeIdentifierSleepAnalysis":
                raw_stage = elem.attrib.get("value", "")
                stage = SLEEP_STAGE_MAP.get(raw_stage)
                if stage is None:
                    continue
                start = parse_date(elem.attrib.get("startDate", ""))
                end = parse_date(elem.attrib.get("endDate", ""))
                try:
                    s = datetime.fromisoformat(start)
                    e = datetime.fromisoformat(end)
                    duration = (e - s).total_seconds() / 60
                except Exception:
                    duration = 0.0
                source = elem.attrib.get("sourceName", "").replace(" ", " ")
                cur.execute(
                    "INSERT INTO sleep (time, end_time, stage, duration_min, source) VALUES (?, ?, ?, ?, ?)",
                    (start, end, stage, duration, source),
                )
                counts["sleep"] = counts.get("sleep", 0) + 1
                continue

            table = RECORD_TYPES.get(rtype)
            if table is None:
                continue

            time = parse_date(elem.attrib.get("startDate", ""))
            try:
                value = float(elem.attrib.get("value", "0"))
            except ValueError:
                value = None
            unit = elem.attrib.get("unit", "")
            source = elem.attrib.get("sourceName", "")
            cur.execute(
                f"INSERT INTO {table} (time, value, unit, source) VALUES (?, ?, ?, ?)",
                (time, value, unit, source),
            )
            counts[table] = counts.get(table, 0) + 1

        elif tag == "Workout":
            activity_raw = elem.attrib.get("workoutActivityType", "")
            activity = WORKOUT_TYPE_MAP.get(
                activity_raw, activity_raw.replace("HKWorkoutActivityType", "")
            )
            start = parse_date(elem.attrib.get("startDate", ""))
            end = parse_date(elem.attrib.get("endDate", ""))
            source = elem.attrib.get("sourceName", "")
            try:
                duration = float(elem.attrib.get("duration", "0"))
            except ValueError:
                duration = None

            distance_km = None
            energy_kcal = None
            for stat in elem.findall("WorkoutStatistics"):
                stype = stat.attrib.get("type", "")
                raw = stat.attrib.get("sum") or stat.attrib.get("average")
                if raw is None:
                    continue
                try:
                    val = float(raw)
                except ValueError:
                    continue
                if stype in (
                    "HKQuantityTypeIdentifierDistanceWalkingRunning",
                    "HKQuantityTypeIdentifierDistanceCycling",
                ):
                    distance_km = val  # WorkoutStatistics の sum は km 単位
                elif stype == "HKQuantityTypeIdentifierActiveEnergyBurned":
                    energy_kcal = val

            cur.execute(
                "INSERT INTO workouts (time, end_time, activity_type, duration_min, distance_km, energy_kcal, source) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (start, end, activity, duration, distance_km, energy_kcal, source),
            )
            counts["workouts"] = counts.get("workouts", 0) + 1

    con.commit()
    con.close()

    print("\n取り込み完了:")
    for table, count in sorted(counts.items(), key=lambda x: -x[1]):
        print(f"  {table}: {count:,} 件")
    print(f"\nDB: {db_path}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("使い方: python3 parse_health.py <export.xml のパス>")
        sys.exit(1)

    xml_file = sys.argv[1]
    if not Path(xml_file).exists():
        print(f"ファイルが見つかりません: {xml_file}")
        sys.exit(1)

    db_file = sys.argv[2] if len(sys.argv) > 2 else "data/health.db"
    main(xml_file, db_file)
