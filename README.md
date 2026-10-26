# Dormant Hooks

A tiny server-only NeoForge 1.21.1 mod: when [ServerCore](https://modrinth.com/mod/servercore)'s
activation range skips an entity's tick, NeoForge's `EntityTickEvent.Pre` and `.Post` do not
fire for that entity either.

On a modded server every mod that listens to `EntityTickEvent` runs for every loaded entity on
every tick, including the far-away ones whose tick ServerCore skips. On our pack the two hooks
cost more than all real mob ticks together, and most of those calls were for skipped ticks.

## What it does

One mixin on `ServerLevel.tickNonPassenger`:

- **Pre** is posted only when ServerCore's `ActivationRange.checkIfActive` says the entity ticks
  this tick. ServerCore's own condition asks again right after and gets the same answer, so it
  still makes its own decision and still runs the inactive tick.
- **Post** is posted only when ServerCore marked the entity active for this tick.

Every tick that really runs still fires both events, including the periodic full ticks of
inactive entities, wake-ups and immunities. Cancelling `Pre` still stops the tick. Players and
ServerCore's excluded entity types are untouched, because ServerCore treats them as always active.

Without ServerCore the mixin is not applied. With activation range turned off it does nothing.

## Requirements

- Minecraft 1.21.1, NeoForge 21.1
- ServerCore 1.5.x (tested with 1.5.19)
- Server only: clients do not need it.

## Measured

Bench with ~690 mobs and no players, spark profile of the server thread:

| | without | with |
|---|---|---|
| `EntityTickEvent.Pre` | 18.4 % | 8.8 % |
| `EntityTickEvent.Post` | 19.6 % | 8.2 % |

A bench-only probe (`tools/probe`) checked every entity on every tick: with the mod, every tick
that ran fired Pre and Post, and no skipped tick fired either.

## Building

`./gradlew build` (JDK 21) puts the jar in `build/libs/`.

## License

MIT
