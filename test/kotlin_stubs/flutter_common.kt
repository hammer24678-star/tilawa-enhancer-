package io.flutter.plugin.common
class MethodChannel(m: Any?, n: String) {
    fun setMethodCallHandler(h: ((MethodCall, Result) -> Unit)?) {}
    fun invokeMethod(m: String, a: Any?) {}
    interface Result {
        fun success(r: Any?)
        fun error(c: String, m: String?, d: Any?)
        fun notImplemented()
    }
    class MethodCall { val method: String = ""; val arguments: Any? = null }
}
