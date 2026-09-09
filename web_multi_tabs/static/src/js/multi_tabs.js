/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";

/* ==========================================================================
 * Web Multi Tabs - Odoo 19 Internal Tab Bar
 *
 * 功能：在 Odoo 内部实现多标签页，适配 PWA / Window Controls Overlay 模式。
 * 架构：
 *   - 配置区（CONFIG）：可调常量集中管理，便于未来扩展
 *   - 调试区：日志开关 + DevTools 快照工具
 *   - PWA/WCO 检测区：判断运行环境
 *   - 标签栏 DOM 管理区：创建/销毁/渲染
 *   - WCO 宽度计算区：根据 CSS env() 校准标签栏宽度
 *   - 溢出检测区：折叠按钮显隐 + 滚动 + 下拉菜单
 *   - 标签操作区：增删改查 + 路由同步
 *   - 事件监听区：resize / geometrychange / display-mode / ResizeObserver
 *   - 初始化区
 *
 * 约束（见模块 AGENTS.md）：
 *   - 首行 `/** @odoo-module **\/` 必须保留：缺标记时本文件不会被转译为
 *     Odoo 模块，代码会被原样拼进 bundle，顶层变量与同 bundle 内其他文件共享
 *     作用域（`tabs` / `log` / `init` 等极易冲突）
 *   - 用户可见文本一律英文 + `_t()`，中文只出现在 i18n/zh_CN.po
 * ========================================================================== */

(function () {
    "use strict";

    /* ======================================================================
     * 配置区 —— 集中管理可调参数，便于功能扩展
     * ====================================================================== */
    var CONFIG = {
        MAX_TABS: 15,                    // 最大标签数，超过后淘汰最旧非活跃标签
        POLL_INTERVAL: 300,              // 路由轮询间隔（ms）
        TITLE_UPDATE_DELAY: 1000,        // 标题更新防抖延迟（ms）
        WCO_CONTROL_WIDTH_FALLBACK: 152, // WCO 窗口控制按钮回退宽度（px）
        WCO_MIN_BAR_WIDTH: 100,          // WCO 标签栏最小宽度（px）
        INIT_DELAY: 500,                 // 初始启动延迟（ms），等待 Odoo DOM 就绪
        HEADER_TIMEOUT: 15000,           // 等待 header 出现的超时（ms）
        RESIZE_OBSERVER_DELAY: 1000,     // ResizeObserver 延迟绑定（ms）
        HOME_REDIRECT_WINDOW: 3000,      // 首页重定向合并的时间窗口（ms）
        DEBUG_STORAGE_KEY_TABS: "debug_tabs",
        DEBUG_STORAGE_KEY_WCO: "debug_wco",
    };

    /* ======================================================================
     * 调试区
     *
     * 开关来源：URL 参数 `?debug_tabs=1` / `?debug_wco=1`，或 localStorage
     * （由 window.__MultiTabsDebug.enable() / disable() 写入）。
     * 用 let 而非 const：运行期要能被 enable() / disable() 改写。
     * ====================================================================== */
    let DEBUG = /debug_tabs=1/.test(window.location.search) || readDebugFlag(CONFIG.DEBUG_STORAGE_KEY_TABS);
    let DEBUG_WCO = /debug_wco=1/.test(window.location.search) || DEBUG || readDebugFlag(CONFIG.DEBUG_STORAGE_KEY_WCO);

    function readDebugFlag(key) {
        try {
            return localStorage.getItem(key) === "1";
        } catch (e) {
            return false;
        }
    }

    function writeDebugFlag(key, on) {
        try {
            if (on) localStorage.setItem(key, "1");
            else localStorage.removeItem(key);
        } catch (e) { /* 隐私模式下 localStorage 不可用，忽略 */ }
    }

    function timestamp() {
        var t = new Date();
        return t.getHours().toString().padStart(2, "0") + ":" +
            t.getMinutes().toString().padStart(2, "0") + ":" +
            t.getSeconds().toString().padStart(2, "0") + "." +
            t.getMilliseconds().toString().padStart(3, "0");
    }

    function log() {
        if (DEBUG) {
            var args = Array.prototype.slice.call(arguments);
            args.unshift("[MultiTabs " + timestamp() + "]");
            console.log.apply(console, args);
        }
    }

    function logWCO() {
        if (DEBUG_WCO) {
            var args = Array.prototype.slice.call(arguments);
            args.unshift("[MultiTabs-WCO " + timestamp() + "]");
            console.log.apply(console, args);
        }
    }

    // 暴露调试工具到 window，供 DevTools Console 手动调用
    window.__MultiTabsDebug = {
        enable: function () {
            DEBUG = true;
            DEBUG_WCO = true;
            writeDebugFlag(CONFIG.DEBUG_STORAGE_KEY_TABS, true);
            writeDebugFlag(CONFIG.DEBUG_STORAGE_KEY_WCO, true);
            console.log("[MultiTabs] debug logs enabled");
        },
        disable: function () {
            DEBUG = false;
            DEBUG_WCO = false;
            writeDebugFlag(CONFIG.DEBUG_STORAGE_KEY_TABS, false);
            writeDebugFlag(CONFIG.DEBUG_STORAGE_KEY_WCO, false);
            console.log("[MultiTabs] debug logs disabled");
        },
        snapshot: function () {
            var info = {
                PWA_MODE: PWA_MODE,
                WCO_MODE: WCO_MODE,
                isPWA: isPWA(),
                isWCOEnabled: isWCOEnabled(),
                innerWidth: window.innerWidth,
                displayMode: readDisplayMode(),
                envValues: safeReadEnv(),
                barElement: barElement ? {
                    inlineWidth: barElement.style.width,
                    computedWidth: safeComputedWidth(barElement),
                    offsetWidth: barElement.offsetWidth,
                    classList: barElement.className,
                } : null,
            };
            console.log("[MultiTabs] state snapshot:", info);
            return info;
        },
        adjust: function () { adjustWCOBarWidth(true); },
        env: function () { return readTitlebarEnvValues(); },
    };

    /* ======================================================================
     * 工具函数
     * ====================================================================== */
    // 复用同一个游离节点做 HTML 转义，避免每次创建 DOM
    var ESCAPE_DIV = document.createElement("div");

    function escapeHtml(s) {
        ESCAPE_DIV.textContent = s;
        return ESCAPE_DIV.innerHTML;
    }

    function escapeAttr(s) {
        return String(s).replace(/"/g, "&quot;").replace(/'/g, "&#39;");
    }

    function beautify(name) {
        return name.replace(/[-_]/g, " ").replace(/\b\w/g, function (l) { return l.toUpperCase(); });
    }

    function safeComputedWidth(el) {
        try { return getComputedStyle(el).width; } catch (e) { return "n/a"; }
    }

    function safeReadEnv() {
        try { return readTitlebarEnvValues(); } catch (e) { return null; }
    }

    /** 规范化 URL：统一首页等价形式，避免末尾斜杠或 /web 入口造成重复标签 */
    function normalizeUrl(url) {
        if (!url) return url;
        // 忽略 hash（Odoo 路由中 hash 通常不用，但保险起见）
        var hashIdx = url.indexOf("#");
        if (hashIdx !== -1) url = url.substring(0, hashIdx);

        var pathAndQuery = url.replace(/\?.*$/, "");
        var query = url.substring(pathAndQuery.length);

        // 首页等价形式统一为 /odoo
        if (pathAndQuery === "/" || pathAndQuery === "/web" || pathAndQuery === "/web/" ||
            pathAndQuery === "/odoo" || pathAndQuery === "/odoo/") {
            return "/odoo";
        }

        // 移除路径末尾的斜杠
        if (pathAndQuery.length > 1 && pathAndQuery.endsWith("/")) {
            pathAndQuery = pathAndQuery.slice(0, -1);
        }
        return pathAndQuery + query;
    }

    /** 读取 CSS env(titlebar-area-*) 的实际计算值（px） */
    function readTitlebarEnvValues() {
        var probe = document.getElementById("o_multi_tabs_wco_probe");
        if (!probe) {
            probe = document.createElement("div");
            probe.id = "o_multi_tabs_wco_probe";
            probe.style.cssText =
                "position:fixed;left:env(titlebar-area-x,0);top:env(titlebar-area-y,0);" +
                "width:env(titlebar-area-width,100%);height:env(titlebar-area-height,36px);" +
                "visibility:hidden;pointer-events:none;z-index:-1;";
            document.body.appendChild(probe);
        }
        var cs = getComputedStyle(probe);
        return {
            left: cs.left, top: cs.top, width: cs.width, height: cs.height,
            leftPx: parseFloat(cs.left) || 0,
            widthPx: parseFloat(cs.width) || 0,
            heightPx: parseFloat(cs.height) || 0,
        };
    }

    /** 读取 display-mode 媒体查询的匹配情况 */
    function readDisplayMode() {
        var modes = ["fullscreen", "standalone", "minimal-ui", "browser"];
        var result = {};
        modes.forEach(function (m) {
            result[m] = window.matchMedia("(display-mode: " + m + ")").matches;
        });
        return result;
    }

    /* ======================================================================
     * PWA / WCO 环境检测
     *
     * WCO（Window Controls Overlay）模式下 display-mode 为
     * "window-controls-overlay" 而非 "standalone"，需一并检测。
     * ====================================================================== */
    function isPWA() {
        return window.matchMedia("(display-mode: standalone)").matches ||
            window.matchMedia("(display-mode: window-controls-overlay)").matches ||
            window.navigator.standalone === true;
    }

    function isWCOEnabled() {
        return isPWA() &&
            "windowControlsOverlay" in navigator &&
            !!navigator.windowControlsOverlay &&
            !!navigator.windowControlsOverlay.visible;
    }

    /* ======================================================================
     * 状态变量
     * ====================================================================== */
    var PWA_MODE = isPWA();
    var WCO_MODE = false;

    var tabs = [];
    var activeTabId = null;
    var nextId = 1;
    var lastUrl = "";
    var barElement = null;
    var pollTimer = null;
    var titleTimer = null;
    var initialized = false;
    var originalDocTitle = document.title;
    var dropdownOpen = false;
    var resizeObserver = null;
    // 首页重定向合并：启动后首次从 /odoo 自动跳转到默认 action（如 Discuss）时，不新建标签
    var homeRedirectHandled = false;
    var startupDeadline = 0;

    // 折叠按钮锁定：从折叠菜单切换标签时保持按钮可见，防止闪烁
    var overflowBtnLocked = false;
    // 缓存溢出状态，仅在变化时操作 DOM
    var lastOverflowState = null;
    // 缓存 WCO env 签名，轮询时检测变化才重算
    var lastWCOSig = "";

    /* ======================================================================
     * 路径名映射表 —— 可扩展：添加新的 Odoo 模块路径即可
     *
     * 写成函数而非常量对象：模块加载时译文尚未就绪，顶层 `_t()` 只能拿到英文，
     * 必须在实际使用时才调用。
     * ====================================================================== */
    function getPathNameMap() {
        return {
            "sales": _t("Sales"), "contacts": _t("Contacts"), "inventory": _t("Inventory"),
            "invoicing": _t("Invoicing"), "accounting": _t("Accounting"), "settings": _t("Settings"),
            "discuss": _t("Discuss"), "calendar": _t("Calendar"), "employees": _t("Employees"),
            "purchase": _t("Purchase"), "manufacturing": _t("Manufacturing"), "project": _t("Project"),
            "crm": _t("CRM"), "website": _t("Website"), "ecommerce": _t("E-commerce"),
            "point-of-sale": _t("Point of Sale"), "spreadsheet": _t("Spreadsheet"),
            "knowledge": _t("Knowledge"), "approvals": _t("Approvals"), "sign": _t("Sign"),
            "expense": _t("Expenses"), "timesheet": _t("Timesheets"), "maintenance": _t("Maintenance"),
            "fleet": _t("Fleet"), "quality": _t("Quality"), "repair": _t("Repair"),
            "survey": _t("Surveys"), "livechat": _t("Live Chat"), "dashboard": _t("Dashboard"),
        };
    }

    /** 从 URL 解析标签显示名称 */
    function getTabNameFromUrl(url) {
        if (!url || url === "/" || url === "/odoo" || url === "/odoo/") return _t("Home");
        try {
            var path = url;
            var idx = path.indexOf("/odoo/");
            path = (idx !== -1) ? path.substring(idx + 6) : path.replace(/^\//, "");
            path = path.replace(/\/+$/, "").replace(/\?.*$/, "");
            if (!path) return _t("Home");

            var parts = path.split("/");
            if (parts[0] && parts[0].startsWith("action-")) {
                return String(_t("Action")) + " #" + parts[0].replace("action-", "");
            }

            var sectionName = getPathNameMap()[parts[0]] || beautify(parts[0]);
            if (parts.length >= 2 && /^\d+$/.test(parts[1]))
                return sectionName + " #" + parts[1];
            if (parts.length >= 2)
                return sectionName + " - " + beautify(parts[1]);
            return sectionName;
        } catch (e) {
            return _t("Page");
        }
    }

    /** 从页面 DOM 提取当前视图标题（面包屑或表单标题） */
    function getCurrentTitle() {
        // 1) 优先读取 Odoo 当前 action 的标题区域（与浏览器页签/面包屑保持一致）
        var actionTitle = document.querySelector(
            ".o_control_panel .o_breadcrumb .active, " +
            ".o_control_panel .o_breadcrumb-item.active, " +
            ".o_control_panel .o_breadcrumb_item:last-child"
        );
        if (actionTitle) {
            var t = actionTitle.textContent.trim();
            if (t && t.length < 80) return t;
        }

        // 2) 回退：取面包屑最后一项
        var bc = document.querySelectorAll(
            ".o_breadcrumb_item, .o_breadcrumb .breadcrumb-item, [class*='breadcrumb'] li"
        );
        if (bc.length > 0) {
            var t = bc[bc.length - 1].textContent.trim();
            if (t && t.length < 80) return t;
        }

        // 3) 表单视图中的标题字段
        var el = document.querySelector(".o_form_view .oe_title .o_field_char, .o_form_view h1 span, .o_form_view .o_field_widget[name='name']");
        if (el) {
            var t = el.textContent.trim();
            if (t && t.length < 80) return t;
        }
        return null;
    }

    function scheduleTitleUpdate() {
        clearTimeout(titleTimer);
        titleTimer = setTimeout(function () {
            var tab = findTabById(activeTabId);
            if (!tab) return;
            var newTitle = getCurrentTitle();
            if (newTitle && newTitle !== tab.name) {
                tab.name = newTitle;
                renderTabBar();
                updateDocTitle();
            }
        }, CONFIG.TITLE_UPDATE_DELAY);
    }

    function updateDocTitle() {
        if (!PWA_MODE) return;
        var tab = findTabById(activeTabId);
        if (tab) document.title = tab.name;
    }

    function findTabById(id) {
        return tabs.find(function (t) { return t.id === id; });
    }

    function getCurrentUrl() {
        return normalizeUrl(window.location.pathname + window.location.search);
    }

    function navigateTo(url) {
        history.pushState({}, "", url);
        window.dispatchEvent(new PopStateEvent("popstate", { state: history.state || {} }));
    }

    /* ======================================================================
     * 标签栏 DOM 管理
     * ====================================================================== */
    function findNavbarHeader() {
        return document.querySelector("header.o_navbar");
    }

    function destroyBar() {
        closeOverflowDropdown();
        if (barElement && barElement.parentNode) {
            barElement.parentNode.removeChild(barElement);
        }
        barElement = null;
        if (resizeObserver) {
            resizeObserver.disconnect();
        }
        // 状态缓存随 DOM 一起失效，否则重建后溢出状态判断会被旧值带偏
        lastOverflowState = null;
    }

    function createBar() {
        barElement = document.createElement("div");
        barElement.id = "o_multi_tabs_bar";
        barElement.className = "o_multi_tabs_bar";

        // 始终挂载到 header.o_navbar 内部，避免移出导致导航栏布局异常。
        // WCO 模式下通过 CSS 控制视觉位置，DOM 不脱离 header。
        var header = findNavbarHeader();
        if (header) {
            header.insertBefore(barElement, header.firstChild);
        } else {
            document.body.insertBefore(barElement, document.body.firstChild);
        }

        // WCO 状态切换会 destroyBar() + createBar()，此时要重新绑定尺寸监听
        if (resizeObserver) {
            resizeObserver.observe(barElement);
        }

        if (WCO_MODE) {
            barElement.classList.add("o_multi_tabs_pwa_wco");
            initWCOBarWidth();
        }
        return barElement;
    }

    /** WCO 模式下设置标签栏初始宽度（优先 CSS env，回退估计值） */
    function initWCOBarWidth() {
        var env = safeReadEnv();
        var w = (env && env.widthPx > 0)
            ? Math.round(env.widthPx) + "px"
            : Math.round(window.innerWidth - CONFIG.WCO_CONTROL_WIDTH_FALLBACK) + "px";
        barElement.style.width = w;
        barElement.style.maxWidth = w;
        adjustWCOBarWidth();
        requestAnimationFrame(function () {
            if (WCO_MODE && barElement) adjustWCOBarWidth();
        });
    }

    /* ======================================================================
     * WCO 宽度计算
     *
     * 优先级：CSS env() > WCO API getBoundingClientRect() > 回退估计值
     * ====================================================================== */
    function adjustWCOBarWidth(forceLog) {
        if (!WCO_MODE || !barElement) return;

        var innerW = window.innerWidth;
        var targetWidth = 0;
        var source = "";

        // 优先级 1：CSS env(titlebar-area-width) —— 浏览器原生计算，最准确
        var env = safeReadEnv();
        if (env && env.widthPx > 0 && env.widthPx < innerW) {
            targetWidth = env.widthPx;
            source = "css-env";
        }

        // 优先级 2：WCO API（部分平台不支持 getBoundingClientRect）
        if (!targetWidth && navigator.windowControlsOverlay) {
            try {
                var rect = navigator.windowControlsOverlay.getBoundingClientRect();
                if (rect) {
                    if (rect.width > 0) {
                        targetWidth = innerW - rect.width;
                        source = "wco-rect.width";
                    } else if (rect.left > 0) {
                        targetWidth = rect.left;
                        source = "wco-rect.left";
                    }
                }
            } catch (e) { /* 不支持，静默跳过 */ }
        }

        // 优先级 3：回退估计值
        if (!targetWidth) {
            targetWidth = innerW - CONFIG.WCO_CONTROL_WIDTH_FALLBACK;
            source = "fallback";
        }

        // 安全下限
        if (targetWidth < CONFIG.WCO_MIN_BAR_WIDTH) targetWidth = CONFIG.WCO_MIN_BAR_WIDTH;
        if (targetWidth > innerW) targetWidth = innerW;

        var w = Math.round(targetWidth) + "px";
        var changed = barElement.style.width !== w;
        if (changed) {
            barElement.style.width = w;
            barElement.style.maxWidth = w;
        }

        if (changed || forceLog) {
            logWCO("adjustWCOBarWidth" + (changed ? " [changed]" : " [forced]") + ":",
                "source:", source, "| target:", w, "| innerWidth:", innerW);
        }
    }

    /* ======================================================================
     * 溢出检测与滚动
     *
     * 可视区域偏移说明：
     *   - 左侧偏移（logoOffset）：WCO 模式下 .o_multi_tabs_logo 作为容器
     *     的 flex 兄弟节点占据左侧空间，但视觉上会遮挡容器最左侧的标签。
     *     激活第一个标签时需额外滚动 logo 宽度，避免被遮挡。
     *   - 右侧偏移（overflowBtnOffset）：.o_multi_tabs_overflow_btn 可见时
     *     占据容器右侧空间，激活最右侧标签时需为其预留宽度。
     *     该偏移与溢出按钮显示逻辑保持一致。
     * ====================================================================== */

    /** 获取 .o_multi_tabs_logo 的实际渲染宽度（仅 WCO 模式下存在且可见） */
    function getLogoWidth() {
        if (!barElement) return 0;
        var logo = barElement.querySelector(".o_multi_tabs_logo");
        if (!logo) return 0;
        // 非 WCO 模式下 logo 通过 display:none 隐藏，offsetWidth 为 0
        return logo.offsetWidth || 0;
    }

    /** 获取 .o_multi_tabs_overflow_btn 可见时的实际宽度 */
    function getOverflowBtnWidth() {
        var btn = getOverflowBtn();
        if (!btn) return 0;
        // 仅当按钮可见（含 o_overflow_visible 类）时才计入偏移
        if (!btn.classList.contains("o_overflow_visible")) return 0;
        return btn.offsetWidth || 0;
    }

    function scrollToActiveTab() {
        var container = getContainer();
        if (!container) return;
        var activeEl = container.querySelector(".o_multi_tab_active");
        if (!activeEl) return;

        // 左侧可视边界偏移：logo 占据的宽度（与 overflow_btn 逻辑对称）
        var logoOffset = getLogoWidth();
        // 右侧可视边界偏移：溢出按钮可见时占据的宽度
        var overflowBtnOffset = getOverflowBtnWidth();

        var tabLeft = activeEl.offsetLeft;
        var tabRight = tabLeft + activeEl.offsetWidth;
        // 可视区域：[scrollLeft + logoOffset, scrollLeft + clientWidth - overflowBtnOffset]
        var viewLeft = container.scrollLeft + logoOffset;
        var viewRight = container.scrollLeft + container.clientWidth - overflowBtnOffset;

        if (tabLeft < viewLeft) {
            // 标签左侧被遮挡（含 logo 遮挡）：向右滚动，使标签左边缘对齐 logo 右侧
            container.scrollLeft = Math.max(0, tabLeft - logoOffset);
        } else if (tabRight > viewRight) {
            // 标签右侧被遮挡：向左滚动，使标签右边缘对齐溢出按钮左侧
            var target = tabRight - container.clientWidth + overflowBtnOffset;
            var max = container.scrollWidth - container.clientWidth;
            container.scrollLeft = Math.max(0, Math.min(target, max));
        }
    }

    function getHiddenTabIds() {
        var container = getContainer();
        if (!container) return [];

        var viewLeft = container.scrollLeft;
        var viewRight = viewLeft + container.clientWidth;
        var hidden = [];

        container.querySelectorAll(".o_multi_tab").forEach(function (el) {
            var tabLeft = el.offsetLeft;
            var tabRight = tabLeft + el.offsetWidth;
            var visibleWidth = Math.min(tabRight, viewRight) - Math.max(tabLeft, viewLeft);
            if (visibleWidth < el.offsetWidth - 2) {
                hidden.push(parseInt(el.dataset.tabId));
            }
        });
        return hidden;
    }

    function checkOverflow() {
        var container = getContainer();
        var btn = getOverflowBtn();
        if (!container || !btn) return;

        var isOverflowing = container.scrollWidth > container.clientWidth + 1;

        if (isOverflowing) {
            if (!btn.classList.contains("o_overflow_visible")) {
                btn.classList.add("o_overflow_visible");
            }
        } else if (!overflowBtnLocked) {
            // 未锁定时才隐藏，防止切换过程中闪烁
            if (btn.classList.contains("o_overflow_visible")) {
                btn.classList.remove("o_overflow_visible");
                closeOverflowDropdown();
            }
        }

        if (lastOverflowState !== isOverflowing) {
            lastOverflowState = isOverflowing;
            log("overflow state:", isOverflowing,
                "scrollWidth:", container.scrollWidth, "clientWidth:", container.clientWidth);
        }

        scrollToActiveTab();
    }

    /* ======================================================================
     * 溢出下拉菜单
     * ====================================================================== */
    function toggleOverflowDropdown() {
        if (dropdownOpen) closeOverflowDropdown();
        else openOverflowDropdown();
    }

    function openOverflowDropdown() {
        var dropdown = getDropdown();
        if (!dropdown) return;

        var hiddenIds = getHiddenTabIds();
        var html = hiddenIds.map(function (tabId) {
            var tab = findTabById(tabId);
            if (!tab) return "";
            var active = tab.id === activeTabId;
            return '<div class="o_multi_tabs_overflow_item' + (active ? " o_overflow_active" : "") + '"'
                + ' data-tab-id="' + tab.id + '">'
                + escapeHtml(tab.name)
                + "</div>";
        }).join("");

        if (!html) {
            closeOverflowDropdown();
            return;
        }

        dropdown.innerHTML = html;
        dropdown.classList.add("o_dropdown_open");
        dropdownOpen = true;

        dropdown.querySelectorAll(".o_multi_tabs_overflow_item").forEach(function (el) {
            el.addEventListener("click", function (ev) {
                ev.stopPropagation();
                var clickedId = parseInt(this.dataset.tabId);
                closeOverflowDropdown();
                // 锁定按钮可见，等切换完成后再决定是否隐藏
                overflowBtnLocked = true;
                switchTab(clickedId);
                requestAnimationFrame(function () {
                    requestAnimationFrame(function () {
                        overflowBtnLocked = false;
                        checkOverflow();
                    });
                });
            });
        });

        setTimeout(function () {
            document.addEventListener("click", onOutsideClick);
        }, 0);
    }

    function closeOverflowDropdown() {
        var dropdown = getDropdown();
        if (dropdown) dropdown.classList.remove("o_dropdown_open");
        dropdownOpen = false;
        document.removeEventListener("click", onOutsideClick);
    }

    function onOutsideClick(ev) {
        var btn = getOverflowBtn();
        if (btn && !btn.contains(ev.target)) closeOverflowDropdown();
    }

    /* ======================================================================
     * 渲染标签栏
     *
     * 首次渲染创建完整 DOM（容器 + 折叠按钮）。
     * 后续渲染只更新容器内标签 HTML，不触碰折叠按钮 DOM，
     * 避免按钮因重建丢失 class 状态而闪烁。
     * ====================================================================== */
    function renderTabBar() {
        var bar = barElement;
        if (!bar || !bar.parentNode) bar = createBar();
        if (!bar) return;

        if (tabs.length === 0) {
            bar.style.display = "none";
            return;
        }
        bar.style.display = "";

        var container = bar.querySelector(".o_multi_tabs_container");
        var overflowBtn = bar.querySelector(".o_multi_tabs_overflow_btn");

        if (!container || !overflowBtn) {
            // 首次渲染：创建完整结构
            // WCO 模式下左侧预留 LOGO 区域（可拖动），非 WCO 模式不显示
            var logoHtml = WCO_MODE
                ? '<div class="o_multi_tabs_logo" title="Odoo"></div>'
                : '';
            bar.innerHTML =
                logoHtml +
                '<div class="o_multi_tabs_container">' + buildTabsInnerHtml() + '</div>' +
                buildOverflowBtnHtml();
            container = bar.querySelector(".o_multi_tabs_container");
            overflowBtn = bar.querySelector(".o_multi_tabs_overflow_btn");
        } else {
            // 后续渲染：只更新容器内标签，保留 LOGO 和折叠按钮 DOM
            container.innerHTML = buildTabsInnerHtml();
        }

        bindTabEvents(container);

        // 折叠按钮点击事件仅绑定一次
        if (overflowBtn && !overflowBtn.__multiTabsBound) {
            overflowBtn.__multiTabsBound = true;
            overflowBtn.addEventListener("click", function (ev) {
                if (ev.target.closest(".o_multi_tabs_overflow_dropdown")) return;
                ev.stopPropagation();
                toggleOverflowDropdown();
            });
        }

        // 等浏览器完成布局后检测溢出
        requestAnimationFrame(function () {
            requestAnimationFrame(checkOverflow);
        });
    }

    /** 构建容器内部的标签 HTML（不含容器 div 本身） */
    function buildTabsInnerHtml() {
        var html = '';
        // 仅剩最后一个标签时不显示关闭按钮，避免关闭后自动新建标签导致出现多个标签页
        var showClose = tabs.length > 1;
        var closeTitle = escapeAttr(_t("Close"));
        for (var i = 0; i < tabs.length; i++) {
            var tab = tabs[i];
            var active = tab.id === activeTabId;
            html += '<div class="o_multi_tab ' + (active ? "o_multi_tab_active" : "") + '"'
                + ' data-tab-id="' + tab.id + '">'
                + '<span class="o_multi_tab_name" title="' + escapeAttr(tab.name) + '">'
                + escapeHtml(tab.name)
                + '</span>'
                + (showClose
                    ? '<button class="o_multi_tab_close" data-tab-id="' + tab.id + '" title="' + closeTitle + '">&times;</button>'
                    : '')
                + '</div>';
        }
        return html;
    }

    function buildOverflowBtnHtml() {
        return '<button class="o_multi_tabs_overflow_btn" title="' + escapeAttr(_t("More tabs")) + '">'
            + '▾'
            + '<div class="o_multi_tabs_overflow_dropdown"></div>'
            + '</button>';
    }

    function bindTabEvents(container) {
        container.querySelectorAll(".o_multi_tab").forEach(function (el) {
            el.addEventListener("click", function (ev) {
                if (ev.target.classList.contains("o_multi_tab_close")) return;
                switchTab(parseInt(this.dataset.tabId));
            });
        });
        container.querySelectorAll(".o_multi_tab_close").forEach(function (el) {
            el.addEventListener("click", function (ev) {
                ev.stopPropagation();
                closeTab(parseInt(this.dataset.tabId));
            });
        });
    }

    /* ======================================================================
     * DOM 查询辅助（缓存查询结果，减少重复 DOM 操作）
     * ====================================================================== */
    function getContainer() {
        return barElement ? barElement.querySelector(".o_multi_tabs_container") : null;
    }

    function getOverflowBtn() {
        return barElement ? barElement.querySelector(".o_multi_tabs_overflow_btn") : null;
    }

    function getDropdown() {
        var btn = getOverflowBtn();
        return btn ? btn.querySelector(".o_multi_tabs_overflow_dropdown") : null;
    }

    /* ======================================================================
     * 标签操作
     * ====================================================================== */
    function switchTab(tabId) {
        var tab = findTabById(tabId);
        if (!tab) return;
        activeTabId = tabId;
        var cur = getCurrentUrl();
        if (normalizeUrl(tab.url) !== cur) navigateTo(tab.url);
        renderTabBar();
        updateDocTitle();
    }

    function closeTab(tabId) {
        var idx = tabs.findIndex(function (t) { return t.id === tabId; });
        if (idx === -1) return;

        // 最后一个标签禁止关闭：避免关闭后自动新建"首页"并触发"消息"标签，导致出现多个标签页
        if (tabs.length <= 1) return;

        tabs.splice(idx, 1);

        // 关闭后切换到相邻标签（关闭总能让出至少一个标签，这里不需要空列表分支）
        var newIdx = Math.min(idx, tabs.length - 1);
        activeTabId = tabs[newIdx].id;
        navigateTo(tabs[newIdx].url);

        renderTabBar();
        updateDocTitle();
    }

    function addTab(url, options) {
        options = options || {};
        if (!url) return;

        url = normalizeUrl(url);

        var existing = tabs.find(function (t) { return normalizeUrl(t.url) === url; });
        if (existing) {
            activeTabId = existing.id;
            renderTabBar();
            updateDocTitle();
            return;
        }

        // 超过上限时淘汰最旧的非活跃标签
        if (tabs.length >= CONFIG.MAX_TABS) {
            var old = tabs.find(function (t) { return t.id !== activeTabId; });
            if (old) tabs.splice(tabs.indexOf(old), 1);
        }

        // 首页标签强制使用 Home，避免 Odoo 默认首页（如 Discuss）的 DOM 标题污染标签名
        var initialName;
        if (options.name) {
            initialName = options.name;
        } else if (url === "/odoo") {
            initialName = String(_t("Home"));
        } else {
            initialName = getCurrentTitle() || getTabNameFromUrl(url);
        }
        tabs.push({ id: nextId++, name: initialName, url: url });
        activeTabId = tabs[tabs.length - 1].id;
        renderTabBar();
        updateDocTitle();
    }

    /* ======================================================================
     * 路由变化检测
     * ====================================================================== */
    function onRouteChange() {
        var url = getCurrentUrl();
        if (url === lastUrl) return;
        lastUrl = url;

        var existing = tabs.find(function (t) { return normalizeUrl(t.url) === url; });
        if (existing) {
            activeTabId = existing.id;
            renderTabBar();
            updateDocTitle();
        } else if (
            !homeRedirectHandled &&
            Date.now() < startupDeadline &&
            tabs.length === 1 &&
            normalizeUrl(tabs[0].url) === "/odoo" &&
            url !== "/odoo"
        ) {
            // Odoo 启动时常把 /odoo 自动替换为 /odoo/discuss 等默认首页 action，
            // 此时应更新现有 Home 标签而不是新建，避免两个标签指向同一页面。
            var tab = tabs[0];
            tab.url = url;
            tab.name = getCurrentTitle() || getTabNameFromUrl(url);
            activeTabId = tab.id;
            homeRedirectHandled = true;
            log("home redirect merged:", url, "-> update tab #" + tab.id);
            renderTabBar();
            updateDocTitle();
        } else {
            addTab(url);
        }
        scheduleTitleUpdate();
    }

    /* ======================================================================
     * WCO 签名 —— 用 CSS env() 值检测变化，避免轮询时无谓重算
     * ====================================================================== */
    function getWCOSig() {
        var env = safeReadEnv();
        return env ? env.widthPx + "x" + env.heightPx + "@" + env.leftPx : "err";
    }

    /* ======================================================================
     * 轮询：路由变化 + WCO 状态检测
     * ====================================================================== */
    function startUrlPolling() {
        if (pollTimer) return;
        pollTimer = setInterval(function () {
            if (getCurrentUrl() !== lastUrl) onRouteChange();

            var shouldCheckWCO = PWA_MODE || ("windowControlsOverlay" in navigator);
            if (!shouldCheckWCO) return;

            // WCO 签名变化时才重新计算宽度
            if (WCO_MODE) {
                var sig = getWCOSig();
                if (sig !== lastWCOSig) {
                    lastWCOSig = sig;
                    adjustWCOBarWidth();
                }
            }

            // WCO 状态切换
            var newWCO = isWCOEnabled();
            if (newWCO !== WCO_MODE) {
                WCO_MODE = newWCO;
                lastWCOSig = "";
                destroyBar();
                createBar();
                if (WCO_MODE) adjustWCOBarWidth();
                renderTabBar();
                scheduleWCORecheck([0, 100, 300, 600, 1000]);
            }
        }, CONFIG.POLL_INTERVAL);
    }

    /** WCO 切换后延迟多次校准，捕捉动画结束后的最终值 */
    function scheduleWCORecheck(delays) {
        delays.forEach(function (delay) {
            setTimeout(function () {
                if (WCO_MODE && barElement) adjustWCOBarWidth();
            }, delay);
        });
    }

    /* ======================================================================
     * History API hook
     *
     * 拦截 pushState / replaceState，在 URL 变化后触发路由检测。
     * Odoo 的页面切换大量使用 pushState，必须 hook 才能捕获。
     * ====================================================================== */
    function hookHistoryAPI() {
        var origPush = history.pushState;
        var origReplace = history.replaceState;

        history.pushState = function (state, title, url) {
            origPush.call(this, state, title, url);
            onRouteChange();
        };
        history.replaceState = function (state, title, url) {
            origReplace.call(this, state, title, url);
            onRouteChange();
        };
    }

    /* ======================================================================
     * 事件监听注册
     * ====================================================================== */
    function registerEventListeners() {
        // ResizeObserver：容器尺寸变化时重新检测溢出（rAF 防抖）
        if (window.ResizeObserver) {
            var rafId = null;
            resizeObserver = new ResizeObserver(function () {
                if (rafId) cancelAnimationFrame(rafId);
                rafId = requestAnimationFrame(function () {
                    if (barElement) checkOverflow();
                });
            });
            setTimeout(function () {
                if (barElement && resizeObserver) {
                    resizeObserver.observe(barElement);
                }
            }, CONFIG.RESIZE_OBSERVER_DELAY);
        }

        // resize 事件：WCO 模式下重新校准宽度
        var resizeRafId = null;
        window.addEventListener("resize", function () {
            if (resizeRafId) cancelAnimationFrame(resizeRafId);
            resizeRafId = requestAnimationFrame(function () {
                var curWCO = isWCOEnabled();
                if (!WCO_MODE && !curWCO) return;
                if (curWCO && !WCO_MODE) WCO_MODE = true;
                adjustWCOBarWidth();
                checkOverflow();
            });
        });

        // WCO geometrychange：标题栏显示/隐藏切换
        if (navigator.windowControlsOverlay) {
            navigator.windowControlsOverlay.addEventListener("geometrychange", function (ev) {
                var nowWCO = isWCOEnabled();
                logWCO("geometrychange | visible:", ev && ev.visible,
                    "| WCO_MODE:", WCO_MODE, "->", nowWCO);

                if (nowWCO !== WCO_MODE) {
                    WCO_MODE = nowWCO;
                    lastWCOSig = "";
                    destroyBar();
                    createBar();
                    renderTabBar();
                }
                if (WCO_MODE) {
                    adjustWCOBarWidth();
                    checkOverflow();
                    scheduleWCORecheck([50, 200, 500]);
                }
            });
        }

        // display-mode 媒体查询变化（辅助检测，日志记录）
        try {
            var onDisplayModeChange = function (ev) {
                logWCO("display-mode changed | media:", ev.media, "| matches:", ev.matches);
            };
            var mqlStandalone = window.matchMedia("(display-mode: standalone)");
            var mqlWCO = window.matchMedia("(display-mode: window-controls-overlay)");
            if (mqlStandalone.addEventListener) {
                mqlStandalone.addEventListener("change", onDisplayModeChange);
                mqlWCO.addEventListener("change", onDisplayModeChange);
            } else if (mqlStandalone.addListener) {
                mqlStandalone.addListener(onDisplayModeChange);
                mqlWCO.addListener(onDisplayModeChange);
            }
        } catch (e) { /* 忽略 */ }
    }

    /* ======================================================================
     * 初始化
     * ====================================================================== */
    function init() {
        if (initialized) return;

        WCO_MODE = isWCOEnabled();
        logWCO("startup | PWA:", PWA_MODE, "| WCO:", WCO_MODE,
            "| innerWidth:", window.innerWidth, "| display-mode:", readDisplayMode());

        // PWA 模式下标记 <html>，触发 CSS 滚动约束规则：
        // 将 html/body 锁定为视口高度，让 .o_action_manager 接管滚动，
        // 避免触摸板滑动导致整个 web 界面向下滚动。
        if (PWA_MODE) {
            document.documentElement.classList.add("o_multi_tabs_pwa");
        }

        // WCO 模式下无需等待 header（标签栏挂到 body 也可工作）
        if (WCO_MODE) {
            doStart();
            return;
        }

        // 非 WCO 模式：等待 header.o_navbar 出现
        if (findNavbarHeader()) {
            doStart();
            return;
        }

        var obs = new MutationObserver(function (_, o) {
            if (findNavbarHeader()) {
                o.disconnect();
                doStart();
            }
        });
        obs.observe(document.body, { childList: true, subtree: true });
        setTimeout(function () {
            obs.disconnect();
            if (!initialized) doStart();
        }, CONFIG.HEADER_TIMEOUT);
    }

    function doStart() {
        if (initialized) return;
        initialized = true;

        hookHistoryAPI();
        window.addEventListener("popstate", function () { onRouteChange(); });

        lastUrl = getCurrentUrl();
        var isHome = lastUrl === "/odoo";
        // 给首页重定向合并一个时间窗口，覆盖 Odoo 启动期间的自动路由跳转
        startupDeadline = Date.now() + CONFIG.HOME_REDIRECT_WINDOW;
        addTab(lastUrl, isHome ? { name: String(_t("Home")) } : undefined);
        startUrlPolling();
        registerEventListeners();
    }

    /* ======================================================================
     * 启动入口
     * ====================================================================== */
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", function () {
            setTimeout(init, CONFIG.INIT_DELAY);
        });
    } else {
        setTimeout(init, CONFIG.INIT_DELAY);
    }
})();
