# c3-gl-generator

Python scripts to generate OpenGL ES and EGL bindings for the C3 language.
This is especially useful for Android.

## Features

- Generates C3 bindings from Khronos XML
- Supports EGL, OpenGL ES, OpenGL and extensions
- Generates:
  - Type aliases
  - Constants
  - Function pointer declarations
  - Runtime symbol loader

## Platform Notes

> Note: This project has been tested only on Android (AArch64/ARM64).
> Other platforms and architectures are untested and may require additional adjustments to compile correctly.

## Usage

```bash
python c3_gl.py --api gles2 --ver 2.0 --out gl.c3l/gl.c3
python c3_egl.py --ext EGL_extension --out egl.c3l/egl.c3
```
Then copy `gl.c3l` and/or `egl.c3l` to `YourProject/lib/`

Before using any OpenGL/EGL functions in your code, you need to initialize the bindings:
```c3
gl::loadSymbols(egl::getProcAddress);
gl::loadSymbols(glfw::getProcAddress);

// Or manually using dynamic library loading
void* eglHandler = libc::dlopen("/system/lib64/libEGL.so", libc::RTLD_LAZY);
egl::getProcAddress = libc::dlsym(eglHandler, "eglGetProcAddress");
```

## Example

An example Android project using these bindings:
- [C3AndroidDemo](https://github.com/lualvsil/C3AndroidDemo)

## License

This project uses Khronos Registry XML files (gl.xml, egl.xml) from the Khronos Group.
These files are licensed under the Apache License 2.0.

See: [OpenGL-Registry](https://github.com/KhronosGroup/OpenGL-Registry)