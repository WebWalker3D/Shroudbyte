# Add project-specific ProGuard rules here.
# Keep kotlinx-serialization metadata so json round-trips work post-shrink.
-keepattributes *Annotation*, InnerClasses
-dontnote kotlinx.serialization.AnnotationsKt
