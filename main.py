"""Run the desktop app, print an example route, or benchmark the solver."""
import argparse
from statistics import median

from companion.model import COLD_WAR, MAP_FILES, MapProfile, Match, World
from companion.solver import Options, find_route


def main(argv=None):
    parser = argparse.ArgumentParser(description="Zombies route companion")
    parser.add_argument("--map", choices=MAP_FILES, default="kino", help="Initial desktop or CLI map")
    sub = parser.add_subparsers(dest="command")
    plan = sub.add_parser("plan",help="Print a route from manual observations")
    plan.add_argument("--goals",nargs="*",default=["power","jug"],metavar="ID")
    plan.add_argument("--points",type=int,default=500)
    plan.add_argument("--zone", help="Starting zone (defaults to map spawn)")
    plan.add_argument("--marker", choices=["crash","pond"], help="Die Maschine marked surface tunnel")
    plan.add_argument("--other-perks", type=int, default=0, help="Held Cold War perks besides Juggernog and Speed Cola")
    plan.add_argument("--cooldown",type=int,default=0,help="Remaining teleporter cooldown in seconds")
    plan.add_argument("--opened",nargs="*",default=[],metavar="DOOR")
    plan.add_argument("--avoid",nargs="*",default=[],metavar="DOOR")
    plan.add_argument("--flags",nargs="*",default=[],metavar="FLAG")
    plan.add_argument("--mode",choices=["economy","speed","balanced"],default="economy")
    plan.add_argument("--policy",choices=["setup","immediate"],default="setup")
    plan.add_argument("--economy-weight",type=int,default=50)
    bench = sub.add_parser("benchmark",help="Measure all objectives from spawn")
    for command in (plan, bench):
        command.add_argument("--map", choices=MAP_FILES, default=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    profile = MapProfile.load(MAP_FILES[args.map])
    if args.command is None:
        try:
            from companion.ui import launch
        except ModuleNotFoundError as err:
            if err.name not in {"PyQt5","PyQt6"}:
                raise
            parser.exit(1,"Install desktop dependencies with: python -m pip install -r requirements.txt\n")
        return launch(profile)
    if args.command == "benchmark":
        initial = profile.initial
        if profile.data["id"] == COLD_WAR:
            initial = Match(World(initial.world.zone, flags=frozenset({"marker_crash"})), initial.points)
            print("Die Maschine scenario: Crash Site tunnel")
        print(f"{profile.data['name']} | all objectives from spawn | median of 10 solver runs | map load excluded")
        for mode in ["Economy","Speed","Balanced"]:
            result = [find_route(profile,initial,profile.goals,Options(mode)) for _ in range(10)]
            last = result[-1]
            print(f"{mode:9} {last.cost:>6,} pts  {last.seconds:>3}s estimated  {last.expanded:>5,} expanded  "
                  f"{median(r.milliseconds for r in result):.1f} ms median")
        return 0
    flags = set(args.flags)
    if args.marker:
        flags.add(f"marker_{args.marker}")
    world = World(args.zone or profile.initial.world.zone, frozenset(args.opened), frozenset(flags),
                  args.cooldown, args.other_perks)
    match = Match(world,args.points)
    try:
        options = Options(args.mode.title(),args.policy.title(),args.economy_weight)
        route = find_route(profile,match,args.goals,options,frozenset(args.avoid))
    except ValueError as exc:
        parser.error(str(exc))
    print(f"{profile.data['name']} | {options.mode} | {options.budget}")
    if route.status == "marker_required":
        print("Set --marker crash or --marker pond from the HUD. Full setup can plan to the reveal.")
        return 2
    if route.status == "visit_required":
        print("Re-enter the next anomaly in-game. Update your zone and aether flag to continue with the part.")
        return 2
    if route.to_marker:
        print("Partial route to the tunnel reveal. Totals cover this segment. Reserve 500 for the tunnel.")
    if route.status == "unreachable":
        print("No route under the selected door restrictions.")
        return 2
    if route.status == "over_budget":
        print(f"Immediate route exceeds balance. Minimum additional points: {route.shortfall:,}.")
        return 2
    if route.status == "no_targets":
        print("Select an objective.")
        return 0
    if route.status == "complete":
        print("Selected objectives already complete.")
    print(f"Remaining spend: {route.cost:,} pts | Estimated time: {route.seconds}s | Additional points: {route.shortfall:,}")
    for i,(step,short) in enumerate(zip(route.steps,route.readiness(match.points)),1):
        status = f"need {short:,} more" if short else "ready"
        print(f"{i:2}. {step.label:<38} {step.cost:>5,} pts  {step.seconds:>2}s  {status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
