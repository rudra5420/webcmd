import asyncio
import json
import logging
import uuid
from typing import Any, Dict, List, Optional
from pathlib import Path

from playwright.async_api import async_playwright, Page, Browser, Playwright, BrowserContext, TimeoutError as PlaywrightTimeoutError

from webcmd.workers.base import (
    BaseWorker,
    WorkerError,
    TransientError,
    PermanentError,
    NeedsHumanError,
    StateMismatchError
)
from webcmd.workers.types import (
    Capability,
    CapabilitySet,
    WorkerContext,
    PreparedAction,
    WorkerResult,
    ObservationRecord,
    PauseResult,
    ResumeResult,
    IdempotencyType,
    RiskLevel,
    SideEffectStatus,
    TrustLevel
)

logger = logging.getLogger(__name__)

class PlaywrightWorker(BaseWorker):
    """
    Playwright worker for browser automation.
    Implements capabilities like navigation, clicking, typing, etc.
    """
    
    def __init__(self, headless: bool = True):
        self.headless = headless
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None

    @property
    def worker_type(self) -> str:
        return "browser.playwright"

    @property
    def worker_name(self) -> str:
        return "Playwright Browser Worker"
        
    async def initialize(self, context: WorkerContext) -> None:
        """Initialize the browser instance lazily."""
        try:
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(headless=self.headless)
            self._context = await self._browser.new_context()
            self._page = await self._context.new_page()
        except Exception as e:
            raise WorkerError(f"Failed to initialize Playwright: {e}") from e

    async def capabilities(self) -> CapabilitySet:
        """Return the supported capabilities."""
        caps = [
            Capability(name="browser.navigate", description="", idempotency=IdempotencyType.IDEMPOTENT, risk_level=RiskLevel.LOW),
            Capability(name="browser.click", description="", idempotency=IdempotencyType.NON_IDEMPOTENT, risk_level=RiskLevel.MEDIUM),
            Capability(name="browser.type", description="", idempotency=IdempotencyType.NON_IDEMPOTENT, risk_level=RiskLevel.MEDIUM),
            Capability(name="browser.screenshot", description="", idempotency=IdempotencyType.IDEMPOTENT, risk_level=RiskLevel.LOW),
            Capability(name="browser.download", description="", idempotency=IdempotencyType.IDEMPOTENT, risk_level=RiskLevel.MEDIUM),
            Capability(name="browser.dom_inspect", description="", idempotency=IdempotencyType.IDEMPOTENT, risk_level=RiskLevel.LOW),
            Capability(name="browser.scroll", description="", idempotency=IdempotencyType.IDEMPOTENT, risk_level=RiskLevel.LOW),
            Capability(name="browser.wait", description="", idempotency=IdempotencyType.IDEMPOTENT, risk_level=RiskLevel.LOW),
        ]
        return CapabilitySet(capabilities=caps)

    async def prepare(self, action: PreparedAction, context: WorkerContext) -> PreparedAction:
        """Prepare the action for execution."""
        return action

    async def execute(self, action: PreparedAction, context: WorkerContext) -> WorkerResult:
        """Execute the browser action."""
        if not self._page:
            raise StateMismatchError("Browser is not initialized")
            
        try:
            if action.capability == "browser.navigate":
                return await self._execute_navigate(action)
            elif action.capability == "browser.click":
                return await self._execute_click(action)
            elif action.capability == "browser.type":
                return await self._execute_type(action)
            elif action.capability == "browser.screenshot":
                return await self._execute_screenshot(action)
            elif action.capability == "browser.download":
                return await self._execute_download(action)
            elif action.capability == "browser.dom_inspect":
                return await self._execute_dom_inspect(action)
            elif action.capability == "browser.scroll":
                return await self._execute_scroll(action)
            elif action.capability == "browser.wait":
                return await self._execute_wait(action)
            else:
                raise PermanentError(f"Unsupported capability: {action.capability}")
        except PlaywrightTimeoutError as e:
            raise TransientError(f"Action timed out: {e}") from e
        except Exception as e:
            raise WorkerError(f"Execution failed: {e}") from e

    async def _execute_navigate(self, action: PreparedAction) -> WorkerResult:
        url = action.parameters.get("url") or action.target
        if not url:
            raise PermanentError("URL is required for browser.navigate")
        
        await self._page.goto(url, wait_until="domcontentloaded", timeout=25000)
        try:
            await self._page.wait_for_load_state("load", timeout=5000)
        except Exception:
            pass
        
        title = ""
        try:
            title = await self._page.title()
        except Exception:
            pass

        obs = ObservationRecord(
            observation_type="browser_url",
            data={"url": self._page.url, "title": title},
            trust_class=TrustLevel.T4_TOOL_OUTPUT
        )
        return WorkerResult(
            status="succeeded",
            outputs={"url": self._page.url, "title": title, "status": "navigated"},
            observations=[obs],
            side_effect_status=SideEffectStatus.APPLIED
        )

    async def _resolve_locator(self, locator_data: Dict[str, Any]) -> tuple[Any, str]:
        """
        Resolve a locator using a hierarchy:
        1. ARIA role + name
        2. text content
        3. CSS selector
        4. XPath
        """
        role = locator_data.get("role")
        name = locator_data.get("name")
        text = locator_data.get("text")
        css = locator_data.get("css")
        xpath = locator_data.get("xpath")
        
        if role:
            loc = self._page.get_by_role(role, name=name)
            if await loc.count() > 0:
                return loc, f"role={role},name={name}"
        if text:
            loc = self._page.get_by_text(text)
            if await loc.count() > 0:
                return loc, f"text={text}"
        if css:
            loc = self._page.locator(css)
            if await loc.count() > 0:
                return loc, f"css={css}"
        if xpath:
            loc = self._page.locator(f"xpath={xpath}")
            if await loc.count() > 0:
                return loc, f"xpath={xpath}"
                
        raise PermanentError(f"Element not found using locator data: {locator_data}")

    async def _execute_click(self, action: PreparedAction) -> WorkerResult:
        locator_data = action.parameters.get("locator", {})
        locator, strategy = await self._resolve_locator(locator_data)
        
        await locator.first.click()
        
        obs = ObservationRecord(
            observation_type="browser_click",
            data={"strategy_used": strategy},
            trust_class=TrustLevel.T4_TOOL_OUTPUT
        )
        return WorkerResult(status="succeeded", outputs={}, observations=[obs], side_effect_status=SideEffectStatus.APPLIED)

    async def _execute_type(self, action: PreparedAction) -> WorkerResult:
        locator_data = action.parameters.get("locator", {})
        text = action.parameters.get("text", "")
        locator, strategy = await self._resolve_locator(locator_data)
        
        await locator.first.fill(text)
        
        obs = ObservationRecord(
            observation_type="browser_type",
            data={"strategy_used": strategy, "text_length": len(text)},
            trust_class=TrustLevel.T4_TOOL_OUTPUT
        )
        return WorkerResult(status="succeeded", outputs={}, observations=[obs], side_effect_status=SideEffectStatus.APPLIED)
        
    async def _execute_screenshot(self, action: PreparedAction) -> WorkerResult:
        path = action.parameters.get("path", "screenshot.png")
        await self._page.screenshot(path=path, full_page=True)
        
        obs = ObservationRecord(
            observation_type="browser_screenshot",
            data={"path": str(path)},
            trust_class=TrustLevel.T4_TOOL_OUTPUT
        )
        return WorkerResult(status="succeeded", outputs={}, observations=[obs], side_effect_status=SideEffectStatus.APPLIED)

    async def _execute_download(self, action: PreparedAction) -> WorkerResult:
        # Simplistic download handling for demonstration
        async with self._page.expect_download() as download_info:
            locator_data = action.parameters.get("locator", {})
            locator, strategy = await self._resolve_locator(locator_data)
            await locator.first.click()
        
        download = await download_info.value
        path = action.parameters.get("path", download.suggested_filename)
        await download.save_as(path)
        
        obs = ObservationRecord(
            observation_type="browser_download",
            data={"path": str(path), "suggested_filename": download.suggested_filename},
            trust_class=TrustLevel.T4_TOOL_OUTPUT
        )
        return WorkerResult(status="succeeded", outputs={}, observations=[obs], side_effect_status=SideEffectStatus.APPLIED)

    async def _execute_dom_inspect(self, action: PreparedAction) -> WorkerResult:
        content = await self._page.content()
        
        obs = ObservationRecord(
            observation_type="browser_dom",
            data={"content_length": len(content), "content": content[:1000]},
            trust_class=TrustLevel.T4_TOOL_OUTPUT
        )
        return WorkerResult(status="succeeded", outputs={}, observations=[obs], side_effect_status=SideEffectStatus.NO_EFFECT)

    async def _execute_scroll(self, action: PreparedAction) -> WorkerResult:
        x = action.parameters.get("x", 0)
        y = action.parameters.get("y", 500)
        await self._page.mouse.wheel(x, y)
        
        obs = ObservationRecord(
            observation_type="browser_scroll",
            data={"x": x, "y": y},
            trust_class=TrustLevel.T4_TOOL_OUTPUT
        )
        return WorkerResult(status="succeeded", outputs={}, observations=[obs], side_effect_status=SideEffectStatus.APPLIED)

    async def _execute_wait(self, action: PreparedAction) -> WorkerResult:
        css = action.parameters.get("css")
        timeout = action.parameters.get("timeout", 30000)
        
        if css:
            await self._page.wait_for_selector(css, timeout=timeout)
            
        obs = ObservationRecord(
            observation_type="browser_wait",
            data={"css": css, "success": True},
            trust_class=TrustLevel.T4_TOOL_OUTPUT
        )
        return WorkerResult(status="succeeded", outputs={}, observations=[obs], side_effect_status=SideEffectStatus.NO_EFFECT)

    async def observe(self, context: WorkerContext) -> List[ObservationRecord]:
        """Observe the current browser state."""
        if not self._page:
            return []
            
        url = self._page.url
        title = await self._page.title()
        
        # Simplistic visible text
        text = await self._page.evaluate("document.body.innerText")
        
        # DOM fingerprint (very simplistic)
        html = await self._page.content()
        dom_hash = hash(html)
        
        obs = ObservationRecord(
            observation_type="browser_state",
            data={
                "url": url,
                "title": title,
                "text_preview": text[:500] if text else "",
                "dom_fingerprint": str(dom_hash)
            },
            trust_class=TrustLevel.T4_TOOL_OUTPUT
        )
        return [obs]

    async def pause(self) -> PauseResult:
        """Pause execution, save cookies and url."""
        if not self._context or not self._page:
            return PauseResult(success=True, state_snapshot={})
            
        cookies = await self._context.cookies()
        url = self._page.url
        
        return PauseResult(
            success=True,
            state_snapshot={"cookies": cookies, "url": url}
        )

    async def resume(self, context: WorkerContext) -> ResumeResult:
        """Resume execution."""
        # Using state from context if available in a real system, but for now just returning success.
        if not self._context or not self._page:
            return ResumeResult(success=False, message="Browser not initialized")
            
        return ResumeResult(success=True)

    async def cancel(self, reason: str) -> None:
        """Cancel current operation."""
        # No specific cancellation logic for playwright simple ops for now
        pass

    async def shutdown(self) -> None:
        """Shutdown playwright and browser."""
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
