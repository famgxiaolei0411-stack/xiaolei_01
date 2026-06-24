"""
Streamlit 菜单汉化工具
=======================
通过注入 JavaScript 将右上角汉堡菜单文字替换为中文。
"""

import streamlit as st

_LOCALIZE_JS = """
<script>
(function() {
    const map = {
        'Clear cache': '清除缓存',
        'Rerun': '重新运行',
        'Settings': '设置',
        'Print': '打印',
        'About': '关于',
        'Report a bug with app': '报告问题',
        'Get help': '获取帮助',
        'Community forum': '社区论坛',
        'Dark theme': '深色主题',
        'Light theme': '浅色主题',
    };
    function walk() {
        document.querySelectorAll('*').forEach(el => {
            if (el.childNodes.length === 1 && el.childNodes[0].nodeType === 3) {
                let t = el.textContent.trim();
                if (map[t]) el.textContent = map[t];
            }
        });
    }
    setTimeout(walk, 500);
    setTimeout(walk, 2000);
})();
</script>
"""


def inject_localize() -> None:
    """注入汉化 JS 脚本。在页面末尾调用一次即可。"""
    st.markdown(_LOCALIZE_JS, unsafe_allow_html=True)
