package io.github.veelume.dormanthooks.mixin;

import com.mojang.logging.LogUtils;
import java.util.List;
import java.util.Set;
import net.neoforged.fml.loading.LoadingModList;
import org.objectweb.asm.tree.ClassNode;
import org.slf4j.Logger;
import org.spongepowered.asm.mixin.extensibility.IMixinConfigPlugin;
import org.spongepowered.asm.mixin.extensibility.IMixinInfo;

/**
 * Applies the mixins only when ServerCore is loaded. ServerCore applies its activation range mixins whenever it is
 * loaded; whether activation range is enabled is decided per tick inside {@code checkIfActive}.
 */
public final class DormantHooksMixinPlugin implements IMixinConfigPlugin {
    private static final Logger LOGGER = LogUtils.getLogger();

    private boolean serverCoreLoaded;

    @Override
    public void onLoad(String mixinPackage) {
        this.serverCoreLoaded = LoadingModList.get().getModFileById("servercore") != null;
        if (this.serverCoreLoaded) {
            LOGGER.info("ServerCore found: EntityTickEvent follows its activation range");
        } else {
            LOGGER.info("ServerCore not found: doing nothing");
        }
    }

    @Override
    public boolean shouldApplyMixin(String targetClassName, String mixinClassName) {
        return this.serverCoreLoaded;
    }

    @Override
    public String getRefMapperConfig() {
        return null;
    }

    @Override
    public void acceptTargets(Set<String> myTargets, Set<String> otherTargets) {
    }

    @Override
    public List<String> getMixins() {
        return null;
    }

    @Override
    public void preApply(String targetClassName, ClassNode targetClass, String mixinClassName, IMixinInfo mixinInfo) {
    }

    @Override
    public void postApply(String targetClassName, ClassNode targetClass, String mixinClassName, IMixinInfo mixinInfo) {
    }
}
