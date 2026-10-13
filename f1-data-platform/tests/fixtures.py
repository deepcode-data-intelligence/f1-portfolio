"""Small, realistic MRData pages (same shape as the Jolpica API) for offline tests."""

VER = {
    "driverId": "max_verstappen",
    "permanentNumber": "3",
    "code": "VER",
    "url": "http://en.wikipedia.org/wiki/Max_Verstappen",
    "givenName": "Max",
    "familyName": "Verstappen",
    "dateOfBirth": "1997-09-30",
    "nationality": "Dutch",
}
NOR = {
    "driverId": "norris",
    "permanentNumber": "4",
    "code": "NOR",
    "url": "http://en.wikipedia.org/wiki/Lando_Norris",
    "givenName": "Lando",
    "familyName": "Norris",
    "dateOfBirth": "1999-11-13",
    "nationality": "British",
}
RED_BULL = {
    "constructorId": "red_bull",
    "url": "https://en.wikipedia.org/wiki/Red_Bull_Racing",
    "name": "Red Bull",
    "nationality": "Austrian",
}
MCLAREN = {
    "constructorId": "mclaren",
    "url": "http://en.wikipedia.org/wiki/McLaren",
    "name": "McLaren",
    "nationality": "British",
}
BAHRAIN = {
    "circuitId": "bahrain",
    "url": "http://en.wikipedia.org/wiki/Bahrain_International_Circuit",
    "circuitName": "Bahrain International Circuit",
    "Location": {"lat": "26.0325", "long": "50.5106", "locality": "Sakhir", "country": "Bahrain"},
}
JEDDAH = {
    "circuitId": "jeddah",
    "url": "http://en.wikipedia.org/wiki/Jeddah_Street_Circuit",
    "circuitName": "Jeddah Corniche Circuit",
    "Location": {
        "lat": "21.6319",
        "long": "39.1044",
        "locality": "Jeddah",
        "country": "Saudi Arabia",
    },
}


def mrdata(total: int, limit: int, offset: int, **tables) -> dict:
    return {
        "xmlns": "",
        "series": "f1",
        "total": str(total),
        "limit": str(limit),
        "offset": str(offset),
        **tables,
    }


def race(
    season: int, rnd: int, name: str, circuit: dict, date: str, results: list | None = None
) -> dict:
    r = {
        "season": str(season),
        "round": str(rnd),
        "url": "",
        "raceName": name,
        "Circuit": circuit,
        "date": date,
        "time": "15:00:00Z",
    }
    if results is not None:
        r["Results"] = results
    return r


def result(
    driver: dict, constructor: dict, position: int, points: str, grid: int, fastest_rank: int
) -> dict:
    return {
        "number": driver["permanentNumber"],
        "position": str(position),
        "positionText": str(position),
        "points": points,
        "Driver": driver,
        "Constructor": constructor,
        "grid": str(grid),
        "laps": "57",
        "status": "Finished",
        "Time": {"millis": "5504742", "time": "1:31:44.742"}
        if position == 1
        else {"millis": "5527185", "time": "+22.457"},
        "FastestLap": {
            "rank": str(fastest_rank),
            "lap": "39",
            "Time": {"time": "1:32.608"},
            "AverageSpeed": {"units": "kph", "speed": "210.383"},
        },
    }


SEASONS_PAGE = mrdata(
    2,
    100,
    0,
    SeasonTable={"Seasons": [{"season": "2023", "url": ""}, {"season": "2024", "url": ""}]},
)

RACES_2024 = mrdata(
    2,
    100,
    0,
    RaceTable={
        "season": "2024",
        "Races": [
            race(2024, 1, "Bahrain Grand Prix", BAHRAIN, "2024-03-02"),
            race(2024, 2, "Saudi Arabian Grand Prix", JEDDAH, "2024-03-09"),
        ],
    },
)
DRIVERS_2024 = mrdata(2, 100, 0, DriverTable={"season": "2024", "Drivers": [VER, NOR]})
CONSTRUCTORS_2024 = mrdata(
    2, 100, 0, ConstructorTable={"season": "2024", "Constructors": [RED_BULL, MCLAREN]}
)

# Results split in two pages of two rows to exercise pagination.
RESULTS_2024_P0 = mrdata(
    4,
    2,
    0,
    RaceTable={
        "season": "2024",
        "Races": [
            race(
                2024,
                1,
                "Bahrain Grand Prix",
                BAHRAIN,
                "2024-03-02",
                [result(VER, RED_BULL, 1, "26", 1, 1), result(NOR, MCLAREN, 2, "18", 2, 2)],
            )
        ],
    },
)
RESULTS_2024_P1 = mrdata(
    4,
    2,
    2,
    RaceTable={
        "season": "2024",
        "Races": [
            race(
                2024,
                2,
                "Saudi Arabian Grand Prix",
                JEDDAH,
                "2024-03-09",
                [result(NOR, MCLAREN, 1, "25", 2, 2), result(VER, RED_BULL, 2, "19", 1, 1)],
            )
        ],
    },
)
SPRINT_2024 = mrdata(
    1,
    100,
    0,
    RaceTable={
        "season": "2024",
        "Races": [
            {
                **race(2024, 1, "Bahrain Grand Prix", BAHRAIN, "2024-03-02"),
                "SprintResults": [result(VER, RED_BULL, 1, "8", 1, 1)],
            }
        ],
    },
)
DRIVER_STANDINGS_2024 = mrdata(
    2,
    100,
    0,
    StandingsTable={
        "season": "2024",
        "round": "2",
        "StandingsLists": [
            {
                "season": "2024",
                "round": "2",
                "DriverStandings": [
                    {
                        "position": "1",
                        "positionText": "1",
                        "points": "53",
                        "wins": "1",
                        "Driver": VER,
                        "Constructors": [RED_BULL],
                    },
                    {
                        "position": "2",
                        "positionText": "2",
                        "points": "43",
                        "wins": "1",
                        "Driver": NOR,
                        "Constructors": [MCLAREN],
                    },
                ],
            }
        ],
    },
)
CONSTRUCTOR_STANDINGS_2024 = mrdata(
    2,
    100,
    0,
    StandingsTable={
        "season": "2024",
        "round": "2",
        "StandingsLists": [
            {
                "season": "2024",
                "round": "2",
                "ConstructorStandings": [
                    {
                        "position": "1",
                        "positionText": "1",
                        "points": "53",
                        "wins": "1",
                        "Constructor": RED_BULL,
                    },
                    {
                        "position": "2",
                        "positionText": "2",
                        "points": "43",
                        "wins": "1",
                        "Constructor": MCLAREN,
                    },
                ],
            }
        ],
    },
)

# URL path (relative to the API base) -> ordered list of pages, as a fake Jolpica would serve them.
ROUTES: dict[str, list[dict]] = {
    "seasons.json": [SEASONS_PAGE],
    "2024/races.json": [RACES_2024],
    "2024/drivers.json": [DRIVERS_2024],
    "2024/constructors.json": [CONSTRUCTORS_2024],
    "2024/results.json": [RESULTS_2024_P0, RESULTS_2024_P1],
    "2024/sprint.json": [SPRINT_2024],
    "2024/driverstandings.json": [DRIVER_STANDINGS_2024],
    "2024/constructorstandings.json": [CONSTRUCTOR_STANDINGS_2024],
}
