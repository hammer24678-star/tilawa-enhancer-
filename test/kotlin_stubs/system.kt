package android.system
object Os {
    fun setenv(k: String, v: String, o: Boolean) {}
    fun chmod(p: String, m: Int) {}
    fun symlink(target: String, linkpath: String) {}
}
