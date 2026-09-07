from astrbot.api.star import Context, Star, register
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api import sp
from astrbot.core.provider.entities import ProviderType


@register("模型人格切换", "suzune", "模型·人格·TTS·STT·识图 一键切换", "3.0")
class FastSwitch(Star):

    def __init__(self, context: Context):
        super().__init__(context)
        self.ctx = context

    # =========================================================================
    # 工具方法
    # =========================================================================

    def _is_admin(self, event: AstrMessageEvent) -> bool:
        return event.is_admin()

    def _require_admin(self, event: AstrMessageEvent):
        """返回 None 表示是管理员，否则返回错误 plain_result"""
        if not event.is_admin():
            return event.plain_result("⚠️ 仅管理员可用")
        return None

    # =========================================================================
    # 帮助
    # =========================================================================

    @filter.command("#帮助")
    async def show_help(self, event: AstrMessageEvent):
        """查看所有可用指令及说明"""
        err = self._require_admin(event)
        if err:
            yield err
            return
        help_text = (
            "📖 模型人格切换 v3.0\n"
            "🔹 模型相关\n"
            "  #模型列表 — 查看所有模型\n"
            "  #模型 <序号> — 切换模型\n"
            "  #当前 — 查看当前模型\n"
            "🔹 人格相关\n"
            "  #人格列表 — 查看所有人格\n"
            "  #人格 <序号> — 切换人格\n"
            "  #当前人格 — 查看当前人格\n"
            "🔹 TTS 语音合成\n"
            "  #TTS列表 — 查看所有 TTS 引擎\n"
            "  #TTS <序号> — 切换 TTS 引擎\n"
            "  #当前TTS — 查看当前 TTS\n"
            "🔹 STT 语音识别\n"
            "  #STT列表 — 查看所有 STT 引擎\n"
            "  #STT <序号> — 切换 STT 引擎\n"
            "  #当前STT — 查看当前 STT\n"
            "🔹 识图模型\n"
            "  #识图列表 — 查看可用识图模型\n"
            "  #识图 <序号> — 切换识图模型\n"
            "  #当前识图 — 查看当前识图模型"
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
        """列出所有已配置的聊天模型，当前模型标记 🔵"""
        err = self._require_admin(event)
        if err:
            yield err
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
        """切换当前会话使用的聊天模型，用法：#模型 <序号>"""
        err = self._require_admin(event)
        if err:
            yield err
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
        """查看当前会话正在使用的聊天模型"""
        err = self._require_admin(event)
        if err:
            yield err
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
        """列出所有已配置的人格，当前人格标记 🔵"""
        err = self._require_admin(event)
        if err:
            yield err
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
        """切换当前会话使用的人格，用法：#人格 <序号>"""
        err = self._require_admin(event)
        if err:
            yield err
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
        """查看当前会话正在使用的人格"""
        err = self._require_admin(event)
        if err:
            yield err
            return
        current_id = await self._get_current_persona_id(event.unified_msg_origin)
        if current_id:
            yield event.plain_result(f"🎭 当前人格：{current_id}")
        else:
            yield event.plain_result("⚠️ 当前未设置人格")

    # =========================================================================
    # TTS 语音合成相关
    # =========================================================================

    def _get_tts_list(self):
        return self.ctx.provider_manager.tts_provider_insts

    def _get_tts_source_name(self, prov):
        meta = prov.meta()
        for pc in self.ctx.provider_manager.providers_config:
            if pc.get("id") == meta.id:
                source_id = pc.get("provider_source_id", "")
                if source_id:
                    return source_id
                break
        return meta.id

    @filter.command("#TTS列表")
    async def show_tts_list(self, event: AstrMessageEvent):
        """列出所有已配置的 TTS 语音合成引擎，当前引擎标记 🔵"""
        err = self._require_admin(event)
        if err:
            yield err
            return
        providers = self._get_tts_list()
        if not providers:
            yield event.plain_result("⚠️ 没有已配置的 TTS 引擎")
            return
        current = self.ctx.provider_manager.curr_tts_provider_inst
        current_id = current.meta().id if current else None
        lines = ["🎤 TTS 语音合成列表\n"]
        for i, prov in enumerate(providers):
            name = self._get_tts_source_name(prov)
            if current_id and prov.meta().id == current_id:
                lines.append(f"{i + 1}. 🔵<{name}> ⬅️\n")
            else:
                lines.append(f"{i + 1}. 🔴<{name}>\n")
        lines.append("\n🟢切换TTS请输入指令：\n#TTS <序号>")
        yield event.plain_result("".join(lines))

    @filter.command("#TTS")
    async def switch_tts(self, event: AstrMessageEvent, idx: str = None):
        """切换当前会话使用的 TTS 语音合成引擎，用法：#TTS <序号>"""
        err = self._require_admin(event)
        if err:
            yield err
            return
        if idx is None:
            yield event.plain_result("⚠️ 用法：#TTS <序号>")
            return
        try:
            idx = int(idx)
        except ValueError:
            yield event.plain_result("⚠️ 序号必须是数字")
            return
        providers = self._get_tts_list()
        if not providers:
            yield event.plain_result("⚠️ 没有已配置的 TTS 引擎")
            return
        if idx < 1 or idx > len(providers):
            yield event.plain_result(f"❌ 序号无效，共 {len(providers)} 个 TTS 引擎")
            return
        prov = providers[idx - 1]
        try:
            await self.ctx.provider_manager.set_provider(
                provider_id=prov.meta().id,
                provider_type=ProviderType.TEXT_TO_SPEECH,
                umo=event.unified_msg_origin,
            )
            yield event.plain_result(f"✅ TTS 已切换到：{self._get_tts_source_name(prov)}")
        except Exception as e:
            yield event.plain_result(f"❌ 切换失败：{e}")

    @filter.command("#当前TTS")
    async def show_current_tts(self, event: AstrMessageEvent):
        """查看当前会话正在使用的 TTS 语音合成引擎"""
        err = self._require_admin(event)
        if err:
            yield err
            return
        current = self.ctx.provider_manager.curr_tts_provider_inst
        if current:
            yield event.plain_result(f"🎤 当前 TTS：{self._get_tts_source_name(current)}")
        else:
            yield event.plain_result("⚠️ 当前未设置 TTS 引擎")

    # =========================================================================
    # STT 语音识别相关
    # =========================================================================

    def _get_stt_list(self):
        return self.ctx.provider_manager.stt_provider_insts

    def _get_stt_source_name(self, prov):
        meta = prov.meta()
        for pc in self.ctx.provider_manager.providers_config:
            if pc.get("id") == meta.id:
                source_id = pc.get("provider_source_id", "")
                if source_id:
                    return source_id
                break
        return meta.id

    @filter.command("#STT列表")
    async def show_stt_list(self, event: AstrMessageEvent):
        """列出所有已配置的 STT 语音识别引擎，当前引擎标记 🔵"""
        err = self._require_admin(event)
        if err:
            yield err
            return
        providers = self._get_stt_list()
        if not providers:
            yield event.plain_result("⚠️ 没有已配置的 STT 引擎")
            return
        current = self.ctx.provider_manager.curr_stt_provider_inst
        current_id = current.meta().id if current else None
        lines = ["🎧 STT 语音识别列表\n"]
        for i, prov in enumerate(providers):
            name = self._get_stt_source_name(prov)
            if current_id and prov.meta().id == current_id:
                lines.append(f"{i + 1}. 🔵<{name}> ⬅️\n")
            else:
                lines.append(f"{i + 1}. 🔴<{name}>\n")
        lines.append("\n🟢切换STT请输入指令：\n#STT <序号>")
        yield event.plain_result("".join(lines))

    @filter.command("#STT")
    async def switch_stt(self, event: AstrMessageEvent, idx: str = None):
        """切换当前会话使用的 STT 语音识别引擎，用法：#STT <序号>"""
        err = self._require_admin(event)
        if err:
            yield err
            return
        if idx is None:
            yield event.plain_result("⚠️ 用法：#STT <序号>")
            return
        try:
            idx = int(idx)
        except ValueError:
            yield event.plain_result("⚠️ 序号必须是数字")
            return
        providers = self._get_stt_list()
        if not providers:
            yield event.plain_result("⚠️ 没有已配置的 STT 引擎")
            return
        if idx < 1 or idx > len(providers):
            yield event.plain_result(f"❌ 序号无效，共 {len(providers)} 个 STT 引擎")
            return
        prov = providers[idx - 1]
        try:
            await self.ctx.provider_manager.set_provider(
                provider_id=prov.meta().id,
                provider_type=ProviderType.SPEECH_TO_TEXT,
                umo=event.unified_msg_origin,
            )
            yield event.plain_result(f"✅ STT 已切换到：{self._get_stt_source_name(prov)}")
        except Exception as e:
            yield event.plain_result(f"❌ 切换失败：{e}")

    @filter.command("#当前STT")
    async def show_current_stt(self, event: AstrMessageEvent):
        """查看当前会话正在使用的 STT 语音识别引擎"""
        err = self._require_admin(event)
        if err:
            yield err
            return
        current = self.ctx.provider_manager.curr_stt_provider_inst
        if current:
            yield event.plain_result(f"🎧 当前 STT：{self._get_stt_source_name(current)}")
        else:
            yield event.plain_result("⚠️ 当前未设置 STT 引擎")

    # =========================================================================
    # 识图模型相关
    # =========================================================================

    def _get_image_caption_providers(self):
        """获取所有支持图片输入的 ChatCompletion 提供商作为识图候选"""
        result = []
        for prov in self.ctx.provider_manager.provider_insts:
            meta = prov.meta()
            # 筛选支持多模态(图片)的提供商
            modalities = getattr(meta, "modalities", None) or []
            if isinstance(modalities, (list, tuple)) and "image" in modalities:
                result.append(prov)
        # 如果没找到带 modalities 标记的，就返回全部（用户自行判断）
        if not result:
            return self.ctx.provider_manager.provider_insts
        return result

    async def _get_current_image_caption_id(self, umo: str) -> str:
        """获取当前生效的识图模型 ID"""
        try:
            cfg = self.ctx.astrbot_config_mgr.get_conf(umo)
            return cfg.get("default_image_caption_provider_id", "") or ""
        except Exception:
            return ""

    @filter.command("#识图列表")
    async def show_image_caption_list(self, event: AstrMessageEvent):
        """列出可用的识图模型（优先显示支持多模态图片输入的模型）"""
        err = self._require_admin(event)
        if err:
            yield err
            return
        providers = self._get_image_caption_providers()
        if not providers:
            yield event.plain_result("⚠️ 没有可用的识图模型")
            return
        current_id = await self._get_current_image_caption_id(event.unified_msg_origin)
        lines = ["👁️ 识图模型列表\n"]
        for i, prov in enumerate(providers):
            name = self._get_source_name(prov)
            if current_id and prov.meta().id == current_id:
                lines.append(f"{i + 1}. 🔵<{name}> ⬅️\n")
            else:
                lines.append(f"{i + 1}. 🔴<{name}>\n")
        lines.append("\n🟢切换识图模型请输入指令：\n#识图 <序号>")
        yield event.plain_result("".join(lines))

    @filter.command("#识图")
    async def switch_image_caption(self, event: AstrMessageEvent, idx: str = None):
        """切换当前会话使用的识图模型，用法：#识图 <序号>"""
        err = self._require_admin(event)
        if err:
            yield err
            return
        if idx is None:
            yield event.plain_result("⚠️ 用法：#识图 <序号>")
            return
        try:
            idx = int(idx)
        except ValueError:
            yield event.plain_result("⚠️ 序号必须是数字")
            return
        providers = self._get_image_caption_providers()
        if not providers:
            yield event.plain_result("⚠️ 没有可用的识图模型")
            return
        if idx < 1 or idx > len(providers):
            yield event.plain_result(f"❌ 序号无效，共 {len(providers)} 个识图模型")
            return
        prov = providers[idx - 1]
        try:
            cfg = self.ctx.astrbot_config_mgr.get_conf(event.unified_msg_origin)
            cfg["default_image_caption_provider_id"] = prov.meta().id
            yield event.plain_result(f"✅ 识图模型已切换到：{self._get_source_name(prov)}")
        except Exception as e:
            yield event.plain_result(f"❌ 切换失败：{e}")

    @filter.command("#当前识图")
    async def show_current_image_caption(self, event: AstrMessageEvent):
        """查看当前会话正在使用的识图模型"""
        err = self._require_admin(event)
        if err:
            yield err
            return
        current_id = await self._get_current_image_caption_id(event.unified_msg_origin)
        if current_id:
            # 尝试找到对应的提供商名字
            for prov in self.ctx.provider_manager.provider_insts:
                if prov.meta().id == current_id:
                    yield event.plain_result(f"👁️ 当前识图：{self._get_source_name(prov)}")
                    return
            yield event.plain_result(f"👁️ 当前识图：{current_id}")
        else:
            yield event.plain_result("⚠️ 当前未设置识图模型（将使用主模型识图）")
