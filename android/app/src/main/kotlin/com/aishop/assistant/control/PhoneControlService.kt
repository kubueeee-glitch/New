package com.aishop.assistant.control

import android.accessibilityservice.AccessibilityService
import android.view.accessibility.AccessibilityEvent
import android.view.accessibility.AccessibilityNodeInfo
import java.util.concurrent.atomic.AtomicReference

/**
 * Włączane przez użytkownika w Ustawienia → Dostępność → AI Shop.
 * Udostępnia statyczny dostęp dla ActionExecutor, który wywołuje gesty/klikanie.
 */
class PhoneControlService : AccessibilityService() {

    override fun onServiceConnected() {
        super.onServiceConnected()
        instanceRef.set(this)
    }

    override fun onDestroy() {
        instanceRef.compareAndSet(this, null)
        super.onDestroy()
    }

    override fun onAccessibilityEvent(event: AccessibilityEvent?) {}
    override fun onInterrupt() {}

    fun findNodesByText(text: String): List<AccessibilityNodeInfo> {
        val root = rootInActiveWindow ?: return emptyList()
        val out = mutableListOf<AccessibilityNodeInfo>()
        collect(root, text.lowercase(), out)
        return out
    }

    private fun collect(node: AccessibilityNodeInfo?, q: String, out: MutableList<AccessibilityNodeInfo>) {
        node ?: return
        val t = node.text?.toString()?.lowercase().orEmpty()
        val d = node.contentDescription?.toString()?.lowercase().orEmpty()
        if (t.contains(q) || d.contains(q)) out += node
        for (i in 0 until node.childCount) collect(node.getChild(i), q, out)
    }

    fun clickFirstMatching(text: String): Boolean {
        val node = findNodesByText(text).firstOrNull { it.isClickable }
            ?: findNodesByText(text).firstOrNull()?.let { firstClickableAncestor(it) }
            ?: return false
        return node.performAction(AccessibilityNodeInfo.ACTION_CLICK)
    }

    private fun firstClickableAncestor(node: AccessibilityNodeInfo): AccessibilityNodeInfo? {
        var cur: AccessibilityNodeInfo? = node
        while (cur != null) {
            if (cur.isClickable) return cur
            cur = cur.parent
        }
        return null
    }

    fun typeIntoFocused(text: String): Boolean {
        val focused = findFocus(AccessibilityNodeInfo.FOCUS_INPUT) ?: return false
        val args = android.os.Bundle().apply {
            putCharSequence(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE, text)
        }
        return focused.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT, args)
    }

    fun scrollDown(): Boolean = scroll(AccessibilityNodeInfo.ACTION_SCROLL_FORWARD)
    fun scrollUp(): Boolean = scroll(AccessibilityNodeInfo.ACTION_SCROLL_BACKWARD)

    private fun scroll(action: Int): Boolean {
        val root = rootInActiveWindow ?: return false
        val target = findScrollable(root) ?: return false
        return target.performAction(action)
    }

    private fun findScrollable(node: AccessibilityNodeInfo?): AccessibilityNodeInfo? {
        node ?: return null
        if (node.isScrollable) return node
        for (i in 0 until node.childCount) {
            val r = findScrollable(node.getChild(i))
            if (r != null) return r
        }
        return null
    }

    fun goBack() = performGlobalAction(GLOBAL_ACTION_BACK)
    fun goHome() = performGlobalAction(GLOBAL_ACTION_HOME)

    companion object {
        private val instanceRef = AtomicReference<PhoneControlService?>(null)
        fun instance(): PhoneControlService? = instanceRef.get()
        fun isEnabled(): Boolean = instance() != null
    }
}
