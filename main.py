from astrbot.api.star import Context, Star, register
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api import sp
from astrbot.core.provider.entities import ProviderType


@register("模型人格切换", "suzune", "模型人格切换", "2.5")
class FastSwitch(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.ctx = context

    # =========================================================================
    # 帮助
    # =========================================================================

    @filter.command("#帮助")
    async def show_help(self, event: AstrMessageEvent):
        if not event.is_admin():
            yield event.plain_result("⚠️ 仅管理员可用")
            return
        help_text = (
            "📖 模型人格切换 v2.5\n"
            "🔹 模型相关\n"
            "  #模型列表 — 查看所有模型\n"
            "  #模型 <序号> — 切换模型\n"
            "  #当前 — 查看当前模型\n"
            "🔹 人格相关\n"
            "  #人格列表 — 查看所有人格\n"
            "  #人格 <序号> — 切换人格\n"
            "  #当前人格 — 查看当前人格"
        )
        yield event.plain_result(help_text)

    # =========================================================================
    # 模型相关
    # =========================================================================

    def _get_provider_list(self):
        return self.ctx.provider_manager.provider_insts

    def _get_source_name(self, prov):
        """获取提供商源唯一ID"""
        meta = prov.meta()
        for pc in self.ctx.provider_manager.providers_config:
            if pc.get("id") == meta.id:
                source_id = pc.get("provider_source_id", "")
                if source_id:
                    return source_id
                break
        return meta.id

    @filter.command("#模型列表")
    async def show_model_list(self, event: AstrMessageEvent):
        if not event.is_admin():
            yield event.plain_result("⚠️ 仅管理员可用")
            return
        providers = self._get_provider_list()
        if not providers:
            yield event.plain_result("⚠️ 没有已配置的模型")
            return

        current_id = None
        try:
            cur = await self.ctx.get_using_provider_async(umo=event.unified_msg_origin)
            if cur:
                current_id = cur.meta().id
        except Exception:
            pass

        lines = ["📋 模型列表\n"]
        for i, prov in enumerate(providers):
            meta = prov.meta()
            name = self._get_source_name(prov)
            if current_id and meta.id == current_id:
                lines.append(f"{i + 1}. 🔵<{name}> ⬅️\n")
            else:
                lines.append(f"{i + 1}. 🔴<{name}>\n")
        lines.append("\n🟢切换模型请输入指令：\n#模型 <序号>")
        yield event.plain_result("".join(lines))

    @filter.command("#模型")
    async def switch_model(self, event: AstrMessageEvent, idx: str = None):
        if not event.is_admin():
            yield event.plain_result("⚠️ 仅管理员可用")
            return
        if idx is None:
            yield event.plain_result("⚠️ 用法：#模型 <序号>")
            return
        try:
            idx = int(idx)
        except ValueError:
            yield event.plain_result("⚠️ 序号必须是数字")
            return

        providers = self._get_provider_list()
        if not providers:
            yield event.plain_result("⚠️ 没有已配置的模型")
            return
        if idx < 1 or idx > len(providers):
            yield event.plain_result(f"❌ 序号无效，共 {len(providers)} 个模型")
            return

        prov = providers[idx - 1]
        try:
            await self.ctx.provider_manager.set_provider(
                provider_id=prov.meta().id,
                provider_type=ProviderType.CHAT_COMPLETION,
                umo=event.unified_msg_origin,
            )
            yield event.plain_result(f"✅ 已切换到：{self._get_source_name(prov)}")
        except Exception as e:
            yield event.plain_result(f"❌ 切换失败：{e}")

    @filter.command("#当前")
    async def show_current(self, event: AstrMessageEvent):
        if not event.is_admin():
            yield event.plain_result("⚠️ 仅管理员可用")
            return
        try:
            cur = await self.ctx.get_using_provider_async(umo=event.unified_msg_origin)
            if cur:
                yield event.plain_result(f"📌 当前：{self._get_source_name(cur)}")
            else:
                yield event.plain_result("⚠️ 当前未设置模型")
        except Exception:
            yield event.plain_result("📌 发送 /provider 查看当前模型")

    # =========================================================================
    # 人格相关
    # =========================================================================

    def _get_persona_list(self):
        """获取所有可用人格列表"""
        return self.ctx.persona_manager.personas_v3

    async def _get_current_persona_id(self, umo: str) -> str | None:
        """获取当前会话生效的人格ID"""
        try:
            session_service_config = (
                await sp.get_async(
                    scope="umo",
                    scope_id=umo,
                    key="session_service_config",
                    default={},
                )
                or {}
            )
            force_id = session_service_config.get("persona_id")
            if force_id:
                return force_id
            cfg = self.ctx.astrbot_config_mgr.get_conf(umo)
            return cfg.get("provider_settings", {}).get("default_personality", "default")
        except Exception:
            return "default"

    @filter.command("#人格列表")
    async def show_persona_list(self, event: AstrMessageEvent):
        if not event.is_admin():
            yield event.plain_result("⚠️ 仅管理员可用")
            return
        personas = self._get_persona_list()
        if not personas:
            yield event.plain_result("⚠️ 没有已配置的人格")
            return

        current_id = await self._get_current_persona_id(event.unified_msg_origin)

        lines = ["🎭 人格列表\n"]
        for i, persona in enumerate(personas):
            name = persona.get("name", "unknown")
            if current_id and name == current_id:
                lines.append(f"{i + 1}. 🔵<{name}> ⬅️\n")
            else:
                lines.append(f"{i + 1}. 🔴<{name}>\n")
        lines.append("\n🟢切换人格请输入指令：\n#人格 <序号>")
        yield event.plain_result("".join(lines))

    @filter.command("#人格")
    async def switch_persona(self, event: AstrMessageEvent, idx: str = None):
        if not event.is_admin():
            yield event.plain_result("⚠️ 仅管理员可用")
            return
        if idx is None:
            yield event.plain_result("⚠️ 用法：#人格 <序号>")
            return
        try:
            idx = int(idx)
        except ValueError:
            yield event.plain_result("⚠️ 序号必须是数字")
            return

        personas = self._get_persona_list()
        if not personas:
            yield event.plain_result("⚠️ 没有已配置的人格")
            return
        if idx < 1 or idx > len(personas):
            yield event.plain_result(f"❌ 序号无效，共 {len(personas)} 个人格")
            return

        target = personas[idx - 1]
        persona_id = target.get("name", "")
        umo = event.unified_msg_origin

        try:
            session_config = (
                await sp.get_async(
                    scope="umo",
                    scope_id=umo,
                    key="session_service_config",
                    default={},
                )
                or {}
            )
            session_config["persona_id"] = persona_id
            await sp.put_async(
                scope="umo",
                scope_id=umo,
                key="session_service_config",
                value=session_config,
            )
            yield event.plain_result(f"✅ 已切换到：{persona_id}")
        except Exception as e:
            yield event.plain_result(f"❌ 切换失败：{e}")

    @filter.command("#当前人格")
    async def show_current_persona(self, event: AstrMessageEvent):
        if not event.is_admin():
            yield event.plain_result("⚠️ 仅管理员可用")
            return
        current_id = await self._get_current_persona_id(event.unified_msg_origin)
        if current_id:
            yield event.plain_result(f"🎭 当前人格：{current_id}")
        else:
            yield event.plain_result("⚠️ 当前未设置人格")
