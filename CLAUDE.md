# dormant-hooks — working notes for Claude

A tiny **server-only** NeoForge 1.21.1 mod for the September 2026 modpack
(`E:\vscode\minecraft\packs\sep2026`). Nothing is written yet: this file is the brief.

## Goal

When ServerCore's activation range skips an entity's tick, NeoForge's
`EntityTickEvent.Pre` and `EntityTickEvent.Post` must not fire for that entity either.

Done means:

- On ticks where ServerCore runs `servercore$inactiveTick` instead of `entity.tick()`,
  no `EntityTickEvent` listener runs for that entity.
- On every tick where the entity really ticks, both events fire as before. That covers
  active entities, the wake-ups, the every-20th-tick full tick of inactive ones, and
  immunities.
- Players, excluded entity types (bosses, Create contraptions, ...; see the pack's
  `config/servercore/config.yml`) and anything ServerCore doesn't handle are untouched.
- If ServerCore is absent or activation range is off, the mod does nothing.
- Measured on the bench (below) and live, with the numbers recorded.

Non-goals: changing which entities ServerCore deactivates, or patching individual
mods. Create Nuclear's radiation hook is handled separately (`mods/create-nuclear`).

## Why: the measurements

All profiles are spark wall-clock profiles (`--force-java-sampler`) of the live server
(16 vCPU VPS; the pack runs Lithium, C2ME, FerriteCore, ModernFix and ServerCore 1.5.19).
Copies are in `tools/profiles/`.

**2026-10-25 20:52, 3 players, ~730 loaded entities** (`2026-10-25_3players`): server
thread 100 % busy, ~15 TPS, median 58 ms/tick. Entity ticking was 43 % of the thread,
and the two hooks alone were 17 %, about 10 ms/tick:

| | % of server thread |
|---|---|
| `EventHooks.fireEntityTickPre` | 8.58 |
| `EventHooks.fireEntityTickPost` | 8.40 |
| all `*.tick()` of mobs together (Villager, Zombie, Creeper, Skeleton, ...) | ~22 |
| ServerCore's own check + `inactiveTick` | 0.97 |

**2026-10-26 06:30, 1 player, 286 loaded entities** (`2026-10-26_1player`): 20 TPS. Entity
ticking was 7.5 ms/tick, of which the hooks took 3.4 ms (Pre 1.8 + Post 1.6). That is
more than all real mob ticks together.

Listeners by mod (1-player profile, % of wall time; at 20 TPS, 1 % = 0.5 ms/tick):

| Event | Mod | Listener | % |
|---|---|---|---|
| Pre | Create Nuclear | `RadiationCapability.onEntityTick` | 1.77 |
| Pre | Malum | `RuntimeEvents.onLivingTick` | 0.64 |
| Pre | Accessories (Aether) | `AccessoriesForge` lambda | 0.61 |
| Pre | Create | | 0.14 |
| Post | Twilight Forest | Traveller's Gear lambda | 0.59 |
| Post | Eternal Starlight | `CommonEvents.onLivingTick` | 0.44 |
| Post | Curios | `CuriosEventHandler.tick` | 0.42 |
| Post | Zeta (Quark) | `ForgeEventsRemapper` lambda | 0.31 |
| Post | Artifacts, Mowzie's, Aether, Sophisticated Backpacks, L2Hostility | | ~0.12-0.23 each |
| both | event bus dispatch itself | | ~0.7 |

**Who is active:** with 1 player, only 21 of 286 entities were within any activation
range (a horizontal box of 16-48 blocks around the player, `tools/box_count.py`).
Inactive entities get a full tick every 20th tick (`tick-interval: 20`). So about 34
entities really tick per tick, yet all ~286 fire both hooks: **~88 % of hook calls are
for ticks ServerCore skips.**

**Expected gain:** ~3 ms/tick with 1 player, ~8-9 ms/tick with 3 players. Hook cost
scales with loaded entities, not with players nearby. This assumes every call costs
about the same. Players are always active and may cost more per call, but there are
only a handful of them.

## How the two mods meet in `ServerLevel.tickNonPassenger`

NeoForge 21.1.265 (the server's version): the profile shows `fireEntityTickPre`,
`fireEntityTickPost` and `<Entity>.tick` as **siblings** directly under
`tickNonPassenger`. As far as I know the patched method is:

```java
entity.tickCount++;                       // ServerCore redirects this (see below)
if (!EventHooks.fireEntityTickPre(entity).isCanceled()) {
    entity.tick();                        // ServerCore wraps this call
    EventHooks.fireEntityTickPost(entity);
}
// then tickPassenger for each passenger: same pattern
```

Check this against the decompiled NeoForge source before writing the mixin.

ServerCore 1.5.19 (`me.wesley1808.servercore.mixin.features.activation_range.ServerLevelMixin`,
checked with javap):

- `@WrapWithCondition servercore$shouldTickEntity(Entity)` around `entity.tick()` in
  `tickNonPassenger`. It calls `ActivationRange.checkIfActive(entity, server.getTickCount())`.
  - If active: `servercore$setInactive(false)`, `tickCount++`, and the tick runs.
  - If not: `servercore$setInactive(true)`, `servercore$inactiveTick()`, and the tick
    is skipped.
- `servercore$shouldTickPassenger(...)` does the same for `tickPassenger`. When
  inactive it also zeroes the passenger's delta movement and positions the rider.
- `servercore$redirectTickCount` replaces vanilla's `tickCount++` with
  `servercore$incFullTickCount()`.
- `servercore$activateEntities` runs at the start of each level tick, every 20 ticks, and
  marks entities near players active (`ActivationRange.activateEntities`).
- `Entity` implements `ActivationEntity`: `servercore$isInactive()`, `servercore$isExcluded()`,
  `servercore$getActivationType()`, `servercore$getActivatedTick()`, ...
- **`checkIfActive` has side effects.** It writes `servercore$setActivatedTick` on
  wake-ups and immunities. On a first reading, a second call in the same tick should
  return the same answer, but verify that before relying on it.

**The ordering problem:** `Post` fires after ServerCore's condition, so it can simply
check `servercore$isInactive()`. `Pre` fires before the condition, so nothing on the
entity says yet whether this tick will run. Options to weigh:

1. Make the decision once, before Pre. Wrap `fireEntityTickPre` and call `checkIfActive`
   there. Store the result for this tick, and make ServerCore's condition reuse it (wrap
   or overwrite `servercore$shouldTickEntity`). That's exact, but couples tightly to
   ServerCore internals.
2. Skip Pre using the previous tick's `servercore$isInactive()`. That's off by at most one
   tick at the edges (activation, wake-up, the 20th-tick full tick). A Pre listener can
   cancel the tick, so check what that means for the edge ticks.
3. Move the Pre call: skip it in the wrapper and fire it from inside ServerCore's
   condition, once the entity is known to be active. That's exact, and it keeps
   cancellation meaning "don't tick".

Whatever is chosen, `EntityTickEvent.Pre` cancellation must still prevent the tick for
active entities.

## Risks to check

- **Sable ships:** sub-levels sit ~20 million blocks out. A mob on a ship is far from
  every player by coordinates, so ServerCore may already treat it as inactive. Check
  how it behaves on a ship before and after, since that is on the pack's open
  in-game list anyway.
- **Listeners that count time for far mobs:** mod effect timers, capability syncs,
  L2Hostility traits, Mowzie's freeze. Vanilla effects already pause for inactive
  entities (they tick inside `LivingEntity.tick`), so pausing mod state the same way is
  consistent. Look out for any listener that does something irreversible or
  world-visible every tick for far mobs.
- **Mixin conflicts:** ServerCore uses MixinExtras on the same method. Prefer
  `@WrapOperation`/`@WrapWithCondition`, which compose, over `@Redirect`/`@Overwrite`.

## Build and test

- Copy postroad's ModDevGradle setup (`E:\vscode\minecraft\mods\postroad`: ModDevGradle 2.x,
  JDK 21, NeoForge 21.1.x), but in plain Java: a mixin mod needs no Kotlin. Mark it
  `side = "server"` in the pack, the same as `servercore.pw.toml`.
- ServerCore as a compile-only dependency. The jar is on Modrinth
  (`servercore-neoforge-1.5.19+1.21.1.jar`), or through the Modrinth maven.
- **Local bench:** `E:\vscode\minecraft\packs\sep2026\server\mc.ps1 <name>` starts a test
  instance. Put the built jar in `server/mods-extra/`, which is mounted at `/mods`.
  Then:
  - `BENCH_RCON_PORT=<port> uv run tools/bench.py setup`: three force-loaded areas
    with ~200 mobs each. With no players near, everything is inactive, the worst case.
  - `... bench.py measure 60`: median and p90 ms/tick.
  - Run it with and without the jar. Take a spark profile too, as on the live server.
  - Stop the instance afterwards (`mc.ps1 <name> -Down`). Two containers plus a client
    don't fit in 32 GB.
- **Profiles:**
  - Start one with `spark profiler start --timeout 180 --force-java-sampler --save-to-file`.
    The file lands in `config/spark/`. spark answers asynchronously, so read its output
    from the server log, not from RCON.
  - Then run `uv run tools/hook_split.py tools/sparkproto <file>`, which prints the
    hook share by mod. Also useful: `callees.py` (self time and callees of a method)
    and `subtree.py`.
- **Live server:** `ssh veelume.icu python3 - "'<command>'" < tools/rc.py` runs an RCON
  command. `tools/box_count.py` counts entities within activation ranges of players.
  Deploying goes through the pack: add a `.pw.toml`, then `cd D:\infra; just deploy minecraft-sep2026`.

## Records

The Firefly project is `dormant-hooks`. The source notes are on the modpack project:
- "EntityTickEvent hooks for ServerCore-inactive entities: profile 2026-10-26"
- "Profile with ServerCore activation range (2026-10-25 20:52)"
- "Mods that hook every entity tick, ranked"
