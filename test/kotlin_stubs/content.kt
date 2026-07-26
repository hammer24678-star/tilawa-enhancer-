package android.content
import java.io.File
import java.io.InputStream
class Context {
    val filesDir: File = File("/")
    val cacheDir: File = File("/")
    val assets: AssetManager = AssetManager()
    val applicationInfo: ApplicationInfo = ApplicationInfo()
    val contentResolver: ContentResolver = ContentResolver()
    fun getExternalFilesDir(t: String?): File? = null
    fun getSharedPreferences(n: String, m: Int): SharedPreferences = SharedPreferences()
}
class AssetManager { fun open(p: String): InputStream = throw RuntimeException() }
class ApplicationInfo { val nativeLibraryDir: String = "/" }
class ContentResolver { fun openInputStream(u: android.net.Uri): InputStream? = null }
class SharedPreferences {
    fun edit(): Editor = Editor()
    fun getBoolean(k: String, d: Boolean): Boolean = d
    class Editor { fun putBoolean(k: String, v: Boolean): Editor = this; fun apply() {} }
}
