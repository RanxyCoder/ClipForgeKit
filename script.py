import os
import core


class Script:
    def __init__(self, input_path):
        if isinstance(input_path, str):
            ex = (".mp4", ".mov", ".mkv", ".avi", ".flv")
            self.input_videos = [os.path.join(input_path, f) for f in os.listdir(input_path) if f.lower().endswith(ex)]
            self.input_videos.sort()
        elif isinstance(input_path, (list, tuple)):
            self.input_videos = list(input_path)
        self.log_correct = ""
        self.log_warning = ""
        self.log_error = ""
        self.cmd_stack = []

    v_params = "codec_name,pix_fmt,width,height,r_frame_rate",
    a_params = "codec_name,sample_rate,channels,channel_layout,sample_fmt"

    def VideoAlign(self,
                   output_dir,
                   video_codec=None,
                   video_quality=None,
                   size=None,
                   r_frame_rate=None,
                   pix_fmt=None,
                   audio_codec=None,
                   sample_rate=None,
                   channels=None,
                   channel_layout=None,
                   sample_fmt=None):
        os.makedirs(output_dir, exist_ok=True)

        # 1. 检测信息
        report = core.FPU().videos_consistency_detect(self.input_videos)
        info_dict = core.FPU().videos_core_info_detect(self.input_videos)
        print(report)

        # 2. 确定目标参数（指定 > 大部队 > None）
        def resolve_param(section, key, user_value):
            if user_value is not None:
                return user_value
            return report[section][key]["majority"]

        target_specs = {
            "video": {
                "codec_name": resolve_param("video", "codec_name", video_codec),
                "pix_fmt": resolve_param("video", "pix_fmt", pix_fmt),
                "width": size[0] if size else report["video"]["width"]["majority"],
                "height": size[1] if size else report["video"]["height"]["majority"],
                "r_frame_rate": r_frame_rate if r_frame_rate else report["video"]["r_frame_rate"]["majority"],
            },
            "audio": {
                "codec_name": resolve_param("audio", "codec_name", audio_codec),
                "sample_rate": resolve_param("audio", "sample_rate", sample_rate),
                "channels": resolve_param("audio", "channels", channels),
                "channel_layout": resolve_param("audio", "channel_layout", channel_layout),
                "sample_fmt": resolve_param("audio", "sample_fmt", sample_fmt),
            }
        }

        # 3. 遍历所有视频
        for f, data in info_dict.items():
            output_file = os.path.join(output_dir, os.path.basename(f))

            v_needs_reencode = any(
                data["video"][k] != target_specs["video"][k]
                for k in ["codec_name", "pix_fmt", "width", "height", "r_frame_rate"]
            )
            a_needs_reencode = any(
                data["audio"][k] != target_specs["audio"][k]
                for k in ["codec_name", "sample_rate", "channels", "channel_layout", "sample_fmt"]
            )

            if not v_needs_reencode and not a_needs_reencode:
                # ✅ 参数一致 → 直接复制
                cmd = f"ffmpeg -i \"{f}\" -c copy \"{output_file}\""
                self.cmd_stack.append(cmd)
                continue

            # ❌ 参数不一致 → 转码
            cmd = f"ffmpeg -i \"{f}\""

            # 视频部分
            if v_needs_reencode:
                # 质量参数
                if video_quality is not None:
                    if target_specs["video"]["codec_name"] in ("h264_nvenc", "hevc_nvenc"):
                        cmd += f" -cq {video_quality}"
                    else:
                        cmd += f" -crf {video_quality}"

                if size:
                    # 尺寸特殊处理，调用 video_margin_fill
                    core.FPU().video_margin_fill(f, output_file, size, target_specs["video"]["codec_name"])
                    continue
                cmd += f" -c:v {target_specs['video']['codec_name']}"
                if pix_fmt:
                    cmd += f" -pix_fmt {pix_fmt}"
                if r_frame_rate:
                    cmd += f" -r {r_frame_rate}"
            else:
                cmd += " -c:v copy"

            # 音频部分
            if a_needs_reencode:
                cmd += f" -c:a {target_specs['audio']['codec_name']}"
                if sample_rate:
                    cmd += f" -ar {sample_rate}"
                if channels:
                    cmd += f" -ac {channels}"
                if channel_layout:
                    cmd += f" -channel_layout {channel_layout}"
            else:
                cmd += " -c:a copy"

            cmd += f" \"{output_file}\""
            self.cmd_stack.append(cmd)

        self.log_correct += f"✅ 已生成 {len(self.cmd_stack)} 条对齐命令。\n"

        return self
