"""
Android → HarmonyOS 转换引擎 CLI 入口。

用法：
    python main.py --src ./architecture-samples --out ./output_hap
"""
import argparse
import json
import os
import sys
import io

# Windows GBK 终端下强制 UTF-8 输出
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


def load_json(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def main():
    parser = argparse.ArgumentParser(
        description="Android 源码 → HarmonyOS 工程转换引擎"
    )
    parser.add_argument("--src", required=True, help="Android 工程根目录")
    parser.add_argument("--out", required=True, help="输出目录（鸿蒙工程）")
    parser.add_argument("--skip-kotlin", action="store_true", help="跳过 Kotlin 源码转换")
    args = parser.parse_args()

    src = os.path.abspath(args.src)
    out = os.path.abspath(args.out)

    if not os.path.isdir(src):
        print(f"[ERROR] 源目录不存在: {src}")
        sys.exit(1)

    # 映射规则文件目录
    mappings_dir = os.path.join(os.path.dirname(__file__), "mappings")

    print(f"\n{'='*60}")
    print(f"  Android → HarmonyOS 转换引擎")
    print(f"  源工程: {src}")
    print(f"  输出到: {out}")
    print(f"{'='*60}\n")

    # ------------------------------------------------------------------ #
    # 1. 扫描工程
    # ------------------------------------------------------------------ #
    from parser import ProjectScanner, ManifestParser, LayoutParser
    from parser import ResourceParser, KotlinParser, GradleParser

    print("[1/7] 扫描 Android 工程结构...")
    scanner = ProjectScanner()
    info = scanner.scan(src)
    print(f"      App 模块: {info.app_module}")
    if info.extra_modules:
        print(f"      子模块:   {len(info.extra_modules)} 个（多模块工程）")
        for m in info.extra_modules[:5]:
            print(f"               - {os.path.relpath(m, src)}")
        if len(info.extra_modules) > 5:
            print(f"               ... 以及 {len(info.extra_modules)-5} 个更多")
    print(f"      布局文件: {len(info.layout_files)} 个")
    print(f"      源文件:   {len(info.source_files)} 个")

    # ------------------------------------------------------------------ #
    # 2. 解析 Manifest
    # ------------------------------------------------------------------ #
    print("[2/7] 解析 AndroidManifest.xml...")
    manifest_parser = ManifestParser()
    info = manifest_parser.parse(info)
    print(f"      包名: {info.package_name}")
    print(f"      Activity: {[a.simple_name for a in info.activities]}")
    print(f"      权限: {len(info.permissions)} 条")

    # ------------------------------------------------------------------ #
    # 3. 解析 Gradle
    # ------------------------------------------------------------------ #
    print("[3/7] 解析 build.gradle...")
    gradle_parser = GradleParser()
    gradle_info = gradle_parser.parse(info.build_gradle)
    if gradle_info.application_id:
        info.package_name = info.package_name or gradle_info.application_id
    info.min_sdk = gradle_info.min_sdk
    info.target_sdk = gradle_info.target_sdk
    print(f"      minSdk={gradle_info.min_sdk}, targetSdk={gradle_info.target_sdk}")
    print(f"      依赖: {len(gradle_info.dependencies)} 条")

    # ------------------------------------------------------------------ #
    # 4. 解析资源
    # ------------------------------------------------------------------ #
    print("[4/7] 解析 res/values/ 资源...")
    resource_parser = ResourceParser()
    res = resource_parser.parse(info.values_dir)
    print(f"      strings: {len(res.strings)}, colors: {len(res.colors)}, dimens: {len(res.dimens)}")

    # ------------------------------------------------------------------ #
    # 5. 解析布局
    # ------------------------------------------------------------------ #
    print("[5/7] 解析 XML 布局...")
    layout_parser = LayoutParser()
    parsed_layouts = layout_parser.parse_all(info.layout_files)
    print(f"      已解析: {len(parsed_layouts)} 个布局")

    # ------------------------------------------------------------------ #
    # 6. 解析源码
    # ------------------------------------------------------------------ #
    classes = []
    if not args.skip_kotlin:
        print("[6/7] 解析 Kotlin/Java 源文件...")
        kotlin_parser = KotlinParser()
        classes = kotlin_parser.parse_all(info.source_files)
        activities = sum(1 for c in classes if c.is_activity)
        fragments = sum(1 for c in classes if c.is_fragment)
        viewmodels = sum(1 for c in classes if c.is_viewmodel)
        print(f"      类: {len(classes)} 个（Activity:{activities} Fragment:{fragments} ViewModel:{viewmodels}）")
    else:
        print("[6/7] 跳过 Kotlin/Java 源文件解析")

    # ------------------------------------------------------------------ #
    # 7. 转换 & 生成
    # ------------------------------------------------------------------ #
    print("[7/7] 转换并生成鸿蒙工程...")

    from transform import (
        ManifestTransform, LayoutTransform, ResourceTransform,
        ImageTransform, KotlinTransform, GradleTransform, SelectorTransform,
    )
    from transform.room_transform import RoomTransform
    from transform.viewmodel_transform import ViewModelTransform
    from transform.navigation_transform import NavigationTransform
    from transform.vector_transform import VectorTransform
    from transform.di_transform import DITransform
    from transform.compose_transform import ComposeTransform
    from transform.flow_transform import FlowTransform
    from transform.service_transform import ServiceTransform
    from transform.retrofit_transform import RetrofitTransform, is_retrofit_file
    from transform.adapter_transform import AdapterTransform
    from transform.media_transform import MediaTransform, is_media_file
    from generator import ProjectGenerator
    from report import ReportGenerator
    from report.report_generator import ConversionStats

    permission_map = load_json(os.path.join(mappings_dir, "permission_map.json"))
    layout_map = load_json(os.path.join(mappings_dir, "layout_map.json"))
    api_map = load_json(os.path.join(mappings_dir, "api_map.json"))
    lifecycle_map_raw = load_json(os.path.join(mappings_dir, "lifecycle_map.json"))
    dependency_map = load_json(os.path.join(mappings_dir, "dependency_map.json"))

    # 合并 activity + fragment 生命周期到一个 flat map
    lifecycle_map = {}
    for section in ("activity", "fragment", "viewmodel"):
        lifecycle_map.update(lifecycle_map_raw.get(section, {}))

    stats = ConversionStats()

    # 创建工程骨架
    gen = ProjectGenerator(out, info)
    gen.create_skeleton()
    # 生成 HAP 签名脚本（解决 9568404 profile cert ≠ signing cert 问题）
    sign_script = gen.generate_sign_script(bundle_name=info.package_name or "com.example.app")
    print(f"      ✓ 签名脚本: {os.path.relpath(sign_script, out)}")

    # Manifest → module.json5 + app.json5
    manifest_tf = ManifestTransform(permission_map)
    manifest_out = manifest_tf.transform(info)
    manifest_tf.write(manifest_out, out)
    print("      ✓ module.json5, app.json5")

    # 资源转换
    res_tf = ResourceTransform()
    res_out = res_tf.transform(res)
    res_tf.write(res_out, out)
    gen.patch_required_resources()   # 补充 DevEco 必要内置资源
    stats.strings_total = len(res.strings)
    stats.colors_total = len(res.colors)
    stats.dimens_total = len(res.dimens)
    print(f"      ✓ string.json, color.json, float.json")

    # 图片复制
    img_tf = ImageTransform()
    copied, skipped = img_tf.transform(info.drawable_dirs, info.mipmap_dirs, out)
    stats.images_copied = copied
    stats.images_skipped = skipped
    stats.warnings.extend(img_tf.warnings)
    print(f"      ✓ 图片: 复制 {copied} 个，跳过 {skipped} 个")

    # Vector Drawable → SVG
    media_dir = os.path.join(out, "entry", "src", "main", "resources", "base", "media")
    vec_tf = VectorTransform()
    vec_converted, vec_failed = vec_tf.convert_all(info.drawable_dirs, media_dir)
    stats.images_copied += vec_converted
    stats.images_skipped = max(0, stats.images_skipped - vec_converted)
    print(f"      ✓ Vector Drawable: {vec_converted} 个 → SVG，{vec_failed} 个转换失败")

    # Selector Drawable → ArkTS StateStyles / 颜色函数
    styles_dir = os.path.join(out, "entry", "src", "main", "ets", "styles")
    sel_tf = SelectorTransform()
    sel_converted, _ = sel_tf.convert_all(info.drawable_dirs, styles_dir)
    if sel_converted:
        print(f"      ✓ Selector Drawable: {sel_converted} 个 → ArkTS StateStyles")

    # 布局转换
    layout_tf = LayoutTransform(layout_map)
    layout_out = layout_tf.transform_all(parsed_layouts)
    gen.write_converted_layouts(layout_out)
    stats.layouts_total = len(parsed_layouts)
    stats.layouts_converted = len(layout_out)
    print(f"      ✓ 布局: {len(layout_out)} 个 → ArkUI")

    # Kotlin/Java 转换（基础规则替换）
    if classes:
        # Compose 文件单独处理
        compose_map_data = load_json(os.path.join(mappings_dir, "compose_map.json"))
        compose_tf = ComposeTransform(compose_map_data)
        compose_classes = [c for c in classes if c.is_compose]
        non_compose_classes = [c for c in classes if not c.is_compose]

        compose_out = {}
        if compose_classes:
            for sc in compose_classes:
                compose_out[sc.file_path] = compose_tf.transform_file(
                    sc.raw_content, os.path.basename(sc.file_path)
                )
            print(f"      ✓ Compose UI: {len(compose_classes)} 个文件 → ArkUI @Component")

        kotlin_tf = KotlinTransform(api_map, lifecycle_map)
        sources_out = kotlin_tf.transform_all(non_compose_classes)

        # Retrofit / OkHttp → axios 网络层转换（优先于 KotlinTransform）
        retrofit_tf = RetrofitTransform()
        retrofit_classes = [c for c in non_compose_classes if is_retrofit_file(c)]
        for sc in retrofit_classes:
            result = retrofit_tf.transform(sc)
            if result:
                sources_out[sc.file_path] = result
        if retrofit_classes:
            print(f"      ✓ Retrofit/OkHttp: {len(retrofit_classes)} 个 → axios 网络服务")

        # Service / BroadcastReceiver / ContentProvider / Worker → HarmonyOS stubs
        svc_tf = ServiceTransform()
        svc_out = svc_tf.transform_all(non_compose_classes)
        if svc_out:
            sources_out.update(svc_out)
            print(f"      ✓ Service/Receiver/Provider: {len(svc_out)} 个 → HarmonyOS Ability 存根")

        # Android Media API → HarmonyOS AVSession / AVPlayer
        media_tf = MediaTransform()
        media_count = 0
        for sc in non_compose_classes:
            if is_media_file(sc.raw_content):
                sources_out[sc.file_path] = media_tf.transform(
                    sources_out.get(sc.file_path, sc.raw_content)
                )
                media_count += 1
        if media_count:
            print(f"      ✓ Media APIs: {media_count} 个文件 → AVSession/AVPlayer")

        # RecyclerView.Adapter / ListAdapter → @Component ForEach
        adapter_tf = AdapterTransform()
        for sc in non_compose_classes:
            if adapter_tf.can_transform(sc.raw_content):
                sources_out[sc.file_path] = adapter_tf.transform(sources_out.get(sc.file_path, sc.raw_content))
        adapter_count = sum(1 for c in non_compose_classes if adapter_tf.can_transform(c.raw_content))
        if adapter_count:
            print(f"      ✓ RecyclerView.Adapter: {adapter_count} 个 → ArkUI ForEach @Component")

        # Flow / StateFlow / SharedFlow UI 层订阅转换
        flow_tf = FlowTransform()
        ui_classes = [c for c in non_compose_classes
                      if not c.is_viewmodel
                      and any("collect" in c.raw_content or "lifecycleScope" in c.raw_content
                              for _ in [None])]
        for sc in ui_classes:
            if sc.file_path in sources_out:
                sources_out[sc.file_path] = flow_tf.transform(sources_out[sc.file_path])
        sources_out.update(compose_out)  # 合并 Compose 转换结果

        # Navigation → Router
        nav_tf = NavigationTransform()
        for path, code in list(sources_out.items()):
            sc = next((c for c in classes if c.file_path == path), None)
            if sc and ("findNavController" in sc.raw_content or "navArgs<" in sc.raw_content):
                sources_out[path] = nav_tf.transform_source(code)

        # ViewModel → @ObservedV2
        vm_tf = ViewModelTransform()
        for sc in classes:
            if sc.is_viewmodel:
                sources_out[sc.file_path] = vm_tf.transform(sc)

        # Room → RelationalStore（生成额外文件）
        room_tf = RoomTransform()
        room_out = room_tf.transform_all(classes)
        data_dir = os.path.join(out, "entry", "src", "main", "ets", "data")
        os.makedirs(data_dir, exist_ok=True)
        for vpath, code in room_out.items():
            fname = os.path.basename(vpath)
            dest = os.path.join(data_dir, fname)
            with open(dest, "w", encoding="utf-8") as f:
                f.write(code)

        # Navigation Router 配置文件
        router_config = nav_tf.generate_router_config(classes)
        router_path = os.path.join(out, "entry", "src", "main", "ets", "pages", "RouterConfig.ets")
        with open(router_path, "w", encoding="utf-8") as f:
            f.write(router_config)

        # Hilt DI → 手动单例
        di_tf = DITransform()
        di_out = di_tf.transform_all(classes)
        for path, code in di_out.items():
            sources_out[path] = code  # 覆盖已有转换结果
        di_dir = os.path.join(out, "entry", "src", "main", "ets", "di")
        os.makedirs(di_dir, exist_ok=True)
        container_code = di_tf.generate_app_container(classes)
        with open(os.path.join(di_dir, "AppContainer.ets"), "w", encoding="utf-8") as f:
            f.write(container_code)
        print(f"      ✓ Hilt DI → AppContainer.ets 手动单例")

        # Activity → 生成可编译 UIAbility 骨架（替换残余 Kotlin 语法版本）
        from transform.ability_generator import generate_ability
        for sc in classes:
            if sc.is_activity:
                sources_out[sc.file_path] = generate_ability(sc, router_page="pages/TasksPage")

        # 最终 ArkTS 语法清理（移除残余 Kotlin 语法）
        from transform.arkts_cleanup import ArkTSCleanup
        cleanup = ArkTSCleanup()
        for path, code in list(sources_out.items()):
            sc = next((c for c in classes if c.file_path == path), None)
            is_ability = sc.is_activity if sc else False
            if not (sc and sc.is_activity):  # Activity 已由 ability_generator 生成，跳过清理
                sources_out[path] = cleanup.clean(code, is_ability=is_ability)

        gen.write_converted_sources(sources_out, classes)

        # 为每个 Fragment 生成 @Entry Page 文件，并更新 main_pages.json
        fragment_classes = [c for c in classes if c.is_fragment]
        gen.write_fragment_pages(fragment_classes)

        # 应用静态覆盖（必须在所有生成步骤之后，避免被覆盖）
        import shutil
        overrides_dir = os.path.join(os.path.dirname(__file__), "static_overrides")
        if os.path.isdir(overrides_dir):
            override_count = 0
            for root, dirs, files in os.walk(overrides_dir):
                for fname in files:
                    src_path = os.path.join(root, fname)
                    rel_path = os.path.relpath(src_path, overrides_dir)
                    dest_path = os.path.join(out, rel_path)
                    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                    shutil.copy2(src_path, dest_path)
                    override_count += 1
            if override_count:
                print(f"      ✓ 静态覆盖: {override_count} 个手动修正文件已应用")

        stats.sources_total = len(classes)
        stats.sources_converted = len(sources_out)
        stats.sources_activity = sum(1 for c in classes if c.is_activity)
        stats.sources_fragment = sum(1 for c in classes if c.is_fragment)
        stats.sources_viewmodel = sum(1 for c in classes if c.is_viewmodel)
        print(f"      ✓ 源码: {len(sources_out)} 个 → ArkTS")
        print(f"      ✓ Room: {len(room_out)} 个数据层文件 → RelationalStore")
        print(f"      ✓ Navigation → Router 配置生成")
        print(f"      ✓ Fragment Pages: {len(fragment_classes)} 个 @Entry 页面生成")

    # Gradle 依赖转换
    gradle_tf = GradleTransform(dependency_map)
    gradle_out = gradle_tf.transform(gradle_info)
    gradle_tf.write(gradle_out, out)
    stats.deps_total = len(gradle_info.dependencies)
    unmapped = gradle_out.get("_unmapped_android_deps", [])
    stats.deps_unmapped = len(unmapped)
    stats.deps_mapped = stats.deps_total - stats.deps_unmapped
    print(f"      ✓ 依赖: {stats.deps_mapped}/{stats.deps_total} 已映射")
    if gradle_tf.write_build_variants_note(gradle_info, out):
        bt_count = len(gradle_info.build_types)
        pf_count = len(gradle_info.product_flavors)
        print(f"      ✓ Build variants: {bt_count} buildTypes, {pf_count} productFlavors → build_variants_note.md")

    # 生成报告
    report_gen = ReportGenerator()
    report_content = report_gen.generate(stats, out)
    todo_count = len(stats.todos)

    print(f"\n{'='*60}")
    print(f"  转换完成！输出目录: {out}")
    print(f"  TODO 项: {todo_count} 处需人工处理")
    print(f"  详细报告: {os.path.join(out, 'conversion_report.md')}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
