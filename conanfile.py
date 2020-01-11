import os
import shutil
from conans import ConanFile, CMake, tools


class TesseractConan(ConanFile):
    name = "tesseract"
    version = "4.1.1"
    description = "Tesseract Open Source OCR Engine"
    url = "http://github.com/bincrafters/conan-tesseract"
    license = "Apache-2.0"
    homepage = "https://github.com/tesseract-ocr/tesseract"
    exports = ["LICENSE.md"]
    exports_sources = ["CMakeLists.txt"]
    generators = "cmake", "cmake_find_package"
    settings = "os", "arch", "compiler", "build_type"
    options = {"shared": [True, False],
               "fPIC": [True, False],
               "with_training": [True, False]}
    default_options = {'shared': False, 'fPIC': True, 'with_training': False}
    _source_subfolder = "source_subfolder"

    requires = "leptonica/1.78.0"

    def source(self):
        sha256 = '2a66ff0d8595bff8f04032165e6c936389b1e5727c3ce5a27b3e059d218db1cb'
        tools.get("https://github.com/tesseract-ocr/tesseract/archive/%s.tar.gz" % self.version, sha256=sha256)
        os.rename("tesseract-" + self.version, self._source_subfolder)
        os.rename(os.path.join(self._source_subfolder, "CMakeLists.txt"),
                  os.path.join(self._source_subfolder, "CMakeListsOriginal.txt"))
        shutil.copy("CMakeLists.txt",
                    os.path.join(self._source_subfolder, "CMakeLists.txt"))

    def config_options(self):
        if self.settings.os == "Windows":
            self.options.remove("fPIC")
        if self.options.with_training:
            # do not enforce failure and allow user to build with system cairo, pango, fontconfig
            self.output.warn("*** Build with training is not yet supported, continue on your own")

    def build(self):
        cmake = CMake(self)
        cmake.definitions['BUILD_TRAINING_TOOLS'] = self.options.with_training
        cmake.definitions["BUILD_SHARED_LIBS"] = self.options.shared
        cmake.definitions["STATIC"] = not self.options.shared
        # Use CMake-based package build and dependency detection, not the pkg-config, cppan or SW
        cmake.definitions['CPPAN_BUILD'] = False
        cmake.definitions['SW_BUILD'] = False

        # avoid accidentally picking up system libarchive
        cmake.definitions['CMAKE_DISABLE_FIND_PACKAGE_LIBARCHIVE'] = True

        # Set Leptonica_DIR to ensure that find_package will be called in original CMake file
        cmake.definitions['Leptonica_DIR'] = self.deps_cpp_info['leptonica'].rootpath
        # Use generated cmake module files
        tools.replace_in_file(
            os.path.join(self._source_subfolder, "CMakeListsOriginal.txt"),
            "find_package(Leptonica ${MINIMUM_LEPTONICA_VERSION} REQUIRED CONFIG)",
            "find_package(Leptonica ${MINIMUM_LEPTONICA_VERSION} REQUIRED)")
        # Variable Leptonica_LIBRARIES does not know about its dependencies which are handled only
        # by exported cmake/pc files which are not used by Conan.
        # Therefore link with exported target from the autogenerated CMake file by the cmake_find_package
        # that contains information about all dependencies
        tools.replace_in_file(
            os.path.join(self._source_subfolder, "CMakeListsOriginal.txt"),
            "${Leptonica_LIBRARIES}",
            "Leptonica::Leptonica")
        # temporary workaround until conan-center-index/pull/648 is merged
        tools.replace_in_file(
            os.path.join(self._source_subfolder, "CMakeListsOriginal.txt"),
            "include_directories(${Leptonica_INCLUDE_DIRS})",
            "include_directories(${Leptonica_INCLUDE_DIRS})\n"
            "include_directories(${CONAN_LEPTONICA_ROOT}/include/leptonica)")

        cmake.configure(source_folder=self._source_subfolder)
        cmake.build()
        cmake.install()
        cmake.patch_config_paths()

        self._fix_absolute_paths()

    def _fix_absolute_paths(self):
        # Fix pc file: cmake does not fill libs.private
        if self.settings.compiler != "Visual Studio":
            libs_private = []
            libs_private.extend(['-L'+path for path in self.deps_cpp_info['leptonica'].lib_paths])
            libs_private.extend(['-l'+lib for lib in self.deps_cpp_info['leptonica'].libs])
            path = os.path.join(self.package_folder, 'lib', 'pkgconfig', 'tesseract.pc')
            tools.replace_in_file(path,
                                  'Libs.private:',
                                  'Libs.private: ' + ' '.join(libs_private))

    def package(self):
        self.copy("LICENSE", src=self._source_subfolder, dst="licenses", ignore_case=True, keep_path=False)
        # remove man pages
        shutil.rmtree(os.path.join(self.package_folder, 'share', 'man'), ignore_errors=True)
        # remove binaries
        for ext in ['', '.exe']:
            try:
                os.remove(os.path.join(self.package_folder, 'bin', 'tesseract'+ext))
            except:
                pass


    def package_info(self):
        self.cpp_info.libs = tools.collect_libs(self)
        if self.settings.os == "Linux":
            self.cpp_info.libs.extend(["pthread"])
        if self.settings.compiler == "Visual Studio":
            if not self.options.shared:
                self.cpp_info.libs.append('ws2_32')
