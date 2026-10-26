package io.github.veelume.dormanthooks.mixin;

import com.llamalad7.mixinextras.injector.v2.WrapWithCondition;
import com.llamalad7.mixinextras.injector.wrapoperation.Operation;
import com.llamalad7.mixinextras.injector.wrapoperation.WrapOperation;
import me.wesley1808.servercore.common.activation_range.ActivationRange;
import me.wesley1808.servercore.common.interfaces.activation_range.ActivationEntity;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.entity.Entity;
import net.neoforged.neoforge.event.tick.EntityTickEvent;
import org.spongepowered.asm.mixin.Final;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Shadow;
import org.spongepowered.asm.mixin.injection.At;

/**
 * Skips NeoForge's {@link EntityTickEvent} for entities whose tick ServerCore's activation range skips.
 *
 * <p>NeoForge's {@code tickNonPassenger} is:
 * <pre>{@code
 * if (!EventHooks.fireEntityTickPre(entity).isCanceled()) {
 *     entity.tick();                          // ServerCore: @WrapWithCondition servercore$shouldTickEntity
 *     EventHooks.fireEntityTickPost(entity);
 * }
 * }</pre>
 * Pre fires before ServerCore decides, so it asks ServerCore's {@code checkIfActive} itself. ServerCore's condition
 * then asks again and gets the same answer: when it returns false it writes nothing, and when it returns true it has
 * set {@code activatedTick} so that the second call returns true as well. Post fires after the decision and reads it
 * back from {@code servercore$isInactive}.
 *
 * <p>Passengers ({@code tickPassenger}) never fire EntityTickEvent in NeoForge 21.1, so they need nothing.
 */
@Mixin(ServerLevel.class)
abstract class ServerLevelMixin {
    @Shadow
    @Final
    private MinecraftServer server;

    @WrapOperation(
            method = "tickNonPassenger",
            at = @At(
                    value = "INVOKE",
                    target = "Lnet/neoforged/neoforge/event/EventHooks;fireEntityTickPre(Lnet/minecraft/world/entity/Entity;)Lnet/neoforged/neoforge/event/tick/EntityTickEvent$Pre;"
            )
    )
    private EntityTickEvent.Pre dormanthooks$firePreIfActive(Entity entity, Operation<EntityTickEvent.Pre> original) {
        if (ActivationRange.checkIfActive(entity, this.server.getTickCount())) {
            return original.call(entity);
        }
        // Not posted and not canceled: ServerCore's condition still runs and does the inactive tick.
        return new EntityTickEvent.Pre(entity);
    }

    @WrapWithCondition(
            method = "tickNonPassenger",
            at = @At(
                    value = "INVOKE",
                    target = "Lnet/neoforged/neoforge/event/EventHooks;fireEntityTickPost(Lnet/minecraft/world/entity/Entity;)V"
            )
    )
    private boolean dormanthooks$firePostIfTicked(Entity entity) {
        return !((ActivationEntity) entity).servercore$isInactive();
    }
}
