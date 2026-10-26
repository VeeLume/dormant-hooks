package io.github.veelume.dormanthooks.probe;

import com.mojang.logging.LogUtils;
import java.util.Collections;
import java.util.IdentityHashMap;
import java.util.Map;
import java.util.Set;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.entity.Entity;
import net.neoforged.fml.common.Mod;
import net.neoforged.neoforge.common.NeoForge;
import net.neoforged.neoforge.event.tick.EntityTickEvent;
import net.neoforged.neoforge.event.tick.ServerTickEvent;
import org.slf4j.Logger;

/**
 * Bench-only check for dormant-hooks, never shipped. Each server tick, every non-passenger entity is sorted by three
 * facts: did its tickCount advance (ServerCore increments it only when the tick runs), was Pre posted for it, was Post
 * posted for it. Every 30 s the tally is logged as "probe ticked/pre/post=count ...".
 *
 * <p>With dormant-hooks: only T/T/T and F/F/F. Without it, ticks ServerCore skips show up as F/T/T.
 */
@Mod("dormant_hooks_probe")
public final class Probe {
    private static final Logger LOGGER = LogUtils.getLogger();
    private static final int REPORT_TICKS = 600;

    private final Set<Entity> pre = Collections.newSetFromMap(new IdentityHashMap<>());
    private final Set<Entity> post = Collections.newSetFromMap(new IdentityHashMap<>());
    private Map<Entity, Integer> lastTickCount = new IdentityHashMap<>();
    private final long[] tally = new long[8];
    private int ticks;

    public Probe() {
        NeoForge.EVENT_BUS.addListener(this::onPre);
        NeoForge.EVENT_BUS.addListener(this::onPost);
        NeoForge.EVENT_BUS.addListener(this::onServerTick);
    }

    private void onPre(EntityTickEvent.Pre event) {
        if (!event.getEntity().level().isClientSide()) {
            this.pre.add(event.getEntity());
        }
    }

    private void onPost(EntityTickEvent.Post event) {
        if (!event.getEntity().level().isClientSide()) {
            this.post.add(event.getEntity());
        }
    }

    private void onServerTick(ServerTickEvent.Post event) {
        Map<Entity, Integer> seen = new IdentityHashMap<>();
        for (ServerLevel level : event.getServer().getAllLevels()) {
            for (Entity entity : level.getAllEntities()) {
                if (entity.isPassenger()) {
                    continue;
                }
                seen.put(entity, entity.tickCount);
                Integer previous = this.lastTickCount.get(entity);
                if (previous == null) {
                    continue;
                }
                int ticked = entity.tickCount != previous ? 4 : 0;
                int pre = this.pre.contains(entity) ? 2 : 0;
                int post = this.post.contains(entity) ? 1 : 0;
                this.tally[ticked | pre | post]++;
            }
        }
        this.lastTickCount = seen;
        this.pre.clear();
        this.post.clear();

        if (++this.ticks % REPORT_TICKS == 0) {
            StringBuilder line = new StringBuilder("probe ticked/pre/post=count over ").append(REPORT_TICKS).append(" ticks:");
            for (int i = 7; i >= 0; i--) {
                line.append(' ')
                        .append((i & 4) != 0 ? 'T' : 'F').append('/')
                        .append((i & 2) != 0 ? 'T' : 'F').append('/')
                        .append((i & 1) != 0 ? 'T' : 'F').append('=').append(this.tally[i]);
                this.tally[i] = 0;
            }
            LOGGER.info(line.toString());
        }
    }
}
