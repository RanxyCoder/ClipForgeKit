import os
import json
import subprocess
from pathlib import Path
from collections import Counter


class ffmpeg:
    def __init__(self, hide_banner=False, overwrite=False, stats=False):
        self.head_cmd = ['ffmpeg']
        self.body_cmd = []
        self.end_cmd = []
        self.combined_cmd = []
        self.log_correct = ""
        self.log_warning = ""
        self.log_error = ""
        self.access_video_codec = False

        if hide_banner:
            self.head_cmd.extend(["-hide_banner"])

        if overwrite:
            self.head_cmd.extend(["-y"])

        if stats:
            self.head_cmd.extend(["-stats"])

    def add_args(self, args: list):
        self.body_cmd.extend(args)

    def f(self, concat=False):
        self.add_args(["-f"])

        if concat:
            self.add_args(["concat"])

        return self

    def input(self, input_path):
        path = Path(input_path)
        if path.is_file():
            self.add_args(["-i", input_path])

        elif path.is_dir():
            files = sorted([str(f) for f in path.iterdir() if f.is_file()])
            for f in files:
                self.add_args(["-i", f])

        elif isinstance(input_path, (list, tuple)):
            for f in input_path:
                if not Path(f).is_file():
                    self.log_error += f"❌ 输入不存在: {f}\n"
                else:
                    self.add_args(["-i", f])
        else:
            self.log_error += "❌ 输入异常\n"

        return self

    def safe(self, r):
        if isinstance(r, int):
            self.add_args(["-safe", f"{r}"])

        return self

    def video_codec(self, codec="copy"):
        self.add_args(["-c:v", codec])
        if codec != "copy":
            self.access_video_codec = True

        return self

    def video_quality(self, quality=None):
        if self.access_video_codec:
            if isinstance(quality, int):
                self.add_args(["-crf", str(quality)])
            elif isinstance(quality, str):
                self.add_args(["-b:v", quality])

        return self

    def preset(self, preset):
        if self.access_video_codec:
            self.add_args(["-preset", preset])

        return self

    def pix_fmt(self, colorspace="yuv", subsampling=420, bit_depth=8):
        if self.access_video_codec:
            colorspace = colorspace.lower()
            if colorspace not in ["yuv", "rgb", "gray"]:
                self.log_error += f"❌ 不支持的 colorspace: {colorspace}\n"
                return self

            if colorspace == "yuv" and bit_depth != 8:
                if bit_depth == 8:
                    pix_fmt_str = f"{colorspace}{subsampling}p"
                else:
                    pix_fmt_str = f"{colorspace}{subsampling}p{bit_depth}"
            elif colorspace == "rgb":
                pix_fmt_str = f"rgb{bit_depth}"
            elif colorspace == "gray":
                pix_fmt_str = f"gray{bit_depth}"
            else:
                pix_fmt_str = f"{colorspace}p{bit_depth}"

            self.add_args(["-pix_fmt", pix_fmt_str])
        else:
            self.log_error += "❌ 编码器未选择，无法进行硬编码。\n"

        return self

    def vf(self, sub=None, si=0, size=None, keep_aspect=None, crop=None, fps=None, pad=None, setsar=False):
        if self.access_video_codec:
            vf_command = ""

            def _interpret(param):
                _path = Path(param).as_posix()
                return _path.replace(":", r"\:")

            if sub is not None:
                vf_command += f"subtitles='{_interpret(sub)}':si={si},"

            if size is not None:
                if keep_aspect == "h" and type(size) is int:
                    vf_command += f"scale=-2:{size}:force_original_aspect_ratio=decrease,"
                elif keep_aspect == "w" and type(size) is int:
                    vf_command += f"scale={size}:-2:force_original_aspect_ratio=decrease,"
                elif keep_aspect is None and isinstance(size, (list, tuple)) and len(size) == 2:
                    vf_command += f"scale={size[0]}:{size[1]},"
                else:
                    self.log_error += f"❌ 尺寸参数输入有误。({size})\n"

            if crop is not None:
                vf_command += f"crop={crop[0]}:{crop[1]}:{crop[2]}:{crop[3]},"

            if pad is not None:
                vf_command += f"pad={pad[0]}:{pad[1]}:(ow-iw)/2:(oh-ih)/2,"

            if fps is not None:
                vf_command += f"fps={fps},"

            if setsar:
                vf_command += f"setsar=1,"

            if vf_command != "":
                self.add_args(["-vf", f"{vf_command[:-1]}"])
            else:
                self.log_warning += "⚠️ 未指定滤镜参数，vf未生效。\n"
        else:
            self.log_error += "❌ 编码器未选择，无法进行硬编码。\n"

        return self

    def audio_codec(self, codec="copy", quality=None):
        self.add_args(["-c:a", codec])

        if quality is not None and codec != "copy":
            if isinstance(quality, int):
                self.add_args(["-q:a", str(quality)])
            elif isinstance(quality, str):
                self.add_args(["-b:a", quality])

        return self

    def audio_sample_fmt(self, fmt):
        self.add_args(["-sample_fmt", str(fmt)])

        return self

    def audio_sample_rate(self, rate=48000):
        self.add_args(["-ar", str(rate)])

        return self

    def audio_channels(self, ch=2):
        self.add_args(["-ac", str(ch)])

        return self

    def audio_channel_layout(self, ch_layout="stereo"):
        self.add_args(["-channel_layout", str(ch_layout)])

        return self

    def map(self, stream_spec):
        self.add_args(["-map", stream_spec])

        return self

    def metadata(self, clean=False, title=None, artist=None, album=None, genre=None, comment=None, creation_time=None):
        if clean:
            self.add_args(["-map_metadata", "-1"])

        m = "-metadata"
        if title is not None:
            self.add_args([m, f"title={title}"])
        if artist is not None:
            self.add_args([m, f"artist={artist}"])
        if album is not None:
            self.add_args([m, f"album={album}"])
        if genre is not None:
            self.add_args([m, f"genre={genre}"])
        if comment is not None:
            self.add_args([m, f"comment={comment}"])
        if creation_time is not None:
            if not isinstance(creation_time, (list, tuple)):
                self.log_error += "❌ creation_time 必须是列表或元组\n"
                return

            if not (3 <= len(creation_time) <= 6):
                self.log_error += "❌ creation_time 必须包含 3~6 个元素\n"
                return

            full_time = list(creation_time) + [0] * (6 - len(creation_time))
            y, m, d, h, mi, s = full_time

            time_str = f"{y}-{m:02d}-{d:02d}T{h:02d}:{mi:02d}:{s:02d}"
            self.add_args(["-metadata", f"creation_time={time_str}"])

        return self

    def output(self, output_path):
        self.end_cmd += [output_path]

        return self

    def final_cmd_combination(self):
        self.combined_cmd = self.head_cmd + self.body_cmd + self.end_cmd

    def cmd(self):
        return self.head_cmd + self.body_cmd + self.end_cmd

    def run(self):
        self.final_cmd_combination()
        if self.log_error == "":
            try:
                subprocess.run(self.combined_cmd)
                self.log_correct += f"✅ 操作完成: {self.combined_cmd[-1]}\n"
            except subprocess.CalledProcessError as e:
                self.log_error += f"❌ 执行失败:, {e}\n"
            except Exception as e:
                self.log_error += f"❌ 未知错误:, {e}\n"

        run_log = "LOG\n"
        run_log += f"️⚙️ 指令组装：{self.combined_cmd}\n"
        run_log += self.log_correct
        run_log += self.log_warning
        run_log += self.log_error
        print(run_log)


class ffprobe:
    def __init__(self, hide_banner=False):
        self.hide_banner = hide_banner
        self.body_cmd = []
        self.head_cmd = ['ffprobe', '-v', 'error']  # 默认安静模式
        self.input_target = None

        if hide_banner:
            self.head_cmd.extend(["-hide_banner"])

    def add_args(self, args: list):
        self.body_cmd.extend(args)

    def input(self, input_path, stream=None):
        if stream is None:
            self.add_args(["-show_streams"])
        elif stream[0] in ["v", "a", "s"] and isinstance(stream[1], int):
            self.add_args(["-select_streams", f"{stream[0]}:{stream[1]}"])

        if not os.path.isfile(input_path):
            raise FileNotFoundError(f"❌ 输入文件不存在: {input_path}")

        self.input_target = [input_path]

        return self

    def show_entries(self, params=None):
        if params is None:
            # 一股脑全拿，包含所有流信息和容器信息
            self.add_args(["-show_format", "-show_streams"])
        elif isinstance(params, str):
            self.add_args(["-show_entries", f"stream=codec_type,index,{params}"])
        else:
            raise FileNotFoundError(f"❌ 输入参数格式有误: 输入格式为{type(params)}，应当为str。")

        return self

    def export(self, fmt="json", core=False):
        """
        执行 ffprobe，返回解析结果
        :param fmt: 输出格式
        :param core: 是否只统计每种流的第 0 个（v0, a0, s0）
        :return: Python dict 或 list
        """
        if not self.input_target:
            raise RuntimeError("❌ 未指定输入文件，请先调用 .input()")

        command = self.head_cmd + self.body_cmd + ["-of", fmt] + self.input_target
        print(command)
        try:
            result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)

            if fmt == "json":
                data = json.loads(result.stdout)
            else:
                data = result.stdout.strip()

            streams = data.get("streams", [])
            if not streams:
                return {} if not core else []

            if core:
                core_streams = []
                found_types = {"video": False, "audio": False, "subtitle": False}
                for s in streams:
                    stype = s.get("codec_type")
                    if stype == "video" and not found_types["video"]:
                        core_streams.append(s)
                        found_types["video"] = True
                    elif stype == "audio" and not found_types["audio"]:
                        core_streams.append(s)
                        found_types["audio"] = True
                    elif stype == "subtitle" and not found_types["subtitle"]:
                        core_streams.append(s)
                        found_types["subtitle"] = True
                return core_streams

            return streams

        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"❌ ffprobe 执行失败: {e.stderr}")


class FPU:
    def __init__(self):
        self.video_core = (
            "codec_name,codec_long_name,codec_type,profile,width,height,coded_width,coded_height,pix_fmt,"
            "field_order,sample_aspect_ratio,display_aspect_ratio,r_frame_rate,avg_frame_rate,time_base,"
            "duration,duration_ts,start_time,nb_frames,bit_rate,index")
        self.audio_core = (
            "codec_name,codec_long_name,codec_type,profile,codec_tag_string,codec_tag,sample_fmt,sample_rate,"
            "channels,channel_layout,bits_per_sample,time_base,duration,duration_ts,nb_frames,bit_rate,index")
        self.log_correct = ""
        self.log_warning = ""
        self.log_error = ""

    def video_margin_fill(self, video_path, output_path, size, codec):
        info = ffprobe().input(video_path, ('v', 0)).show_entries("width,height").export(core=True)
        width, height = info["width"], info["height"]

        video_ratio = width / height
        output_ratio = size[0] / size[1]

        keep_aspect = None
        pad = None

        if abs(video_ratio - output_ratio) < 1e-6:
            align = size
            self.log_warning += f"⚠️ {video_path}视频流比例与目标相同。\n"
        else:
            keep_aspect = "h" if video_ratio < output_ratio else "w"
            align = size[0] if keep_aspect == "w" else size[1]
            pad = size

        exe = ffmpeg().input(video_path)
        exe.video_codec(codec=codec)
        exe.vf(size=align, keep_aspect=keep_aspect, setsar=True, pad=pad)
        exe.output(output_path)

        return exe

    def videos_core_info_detect(self, input_videos):
        def _fps_transform(info_fps):
            num, den = map(int, info_fps.split("/"))
            fps = num / den if den else 0

            return fps

        info_data = {}

        for iv in input_videos:
            info = ffprobe().input(iv)
            info.show_entries(self.video_core + self.audio_core)
            info = info.export(core=True)

            v_data = {}
            for vi in self.video_core.split(","):
                if vi not in ["r_frame_rate", "avg_frame_rate"]:
                    v_data[vi] = info[0][vi]
                else:
                    v_data[vi] = _fps_transform(info[0][vi])

            a_data = {}
            for ai in self.audio_core.split(","):
                a_data[ai] = info[1][ai]

            s_data = {"video": v_data, "audio": a_data}
            info_data[iv] = s_data

        self.log_correct += f"✅ {len(info_data)}个项目已侦测。\n"

        return info_data

    def videos_consistency_detect(self, input_videos, v_params=None, a_params=None):
        if v_params is None:
            v_params = self.video_core
        if a_params is None:
            a_params = self.audio_core

        info_dict = self.videos_core_info_detect(input_videos)
        report = {"video": {}, "audio": {}, "consistency": True, "outliers_global": {}}

        def _params_list(params):
            return [p.strip() for p in params.split(",") if p.strip()]

        video_keys = _params_list(v_params)
        audio_keys = _params_list(a_params)

        outliers_global = {}

        # 遍历两个维度
        for section, keys in [("video", video_keys), ("audio", audio_keys)]:
            for key in keys:
                values = {}
                for file, data in info_dict.items():
                    values[file] = data[section][key]

                # 统计出现次数
                counter = Counter(values.values())
                majority, count = counter.most_common(1)[0]

                # 找出不合群的
                outliers = {f: v for f, v in values.items() if v != majority}

                # 是否完全一致
                consensus = (count == len(values))
                if not consensus:
                    report["consistency"] = False

                # 填充参数报告
                report[section][key] = {
                    "majority": majority,
                    "consensus": consensus,
                    "outliers": outliers
                }

                # 汇总到全局 outliers_global
                for f, v in outliers.items():
                    if f not in outliers_global:
                        outliers_global[f] = {"video": {}, "audio": {}}
                    outliers_global[f][section][key] = v

        report["outliers_global"] = outliers_global

        self.log_correct += f"✅ 视频一致性侦测完毕。\n"

        return report

    def concat_time_sequence(self, input_path, output_path):
        def _concat_list(videos_list, text_path):
            with open(text_path, "w", encoding="utf-8") as f:
                for vp in videos_list:
                    f.write(f"file '{vp}'\n")

        input_files = []
        if isinstance(input_path, str):
            ex = (".mp4", ".mov", ".mkv", ".avi", ".flv")
            input_files = [os.path.join(input_path, f) for f in os.listdir(input_path) if f.lower().endswith(ex)]
            input_files.sort()
        elif isinstance(input_path, (list, tuple)):
            input_files = list(input_path)
        else:
            self.log_error += "❌ 输入规格有误，输入应为视频源列表或目录源。\n"

        if len(input_files) < 2:
            self.log_error += "❌ 输入规格有误，目录源文件数量应为两个即以上。\n"

        output_dir = os.path.dirname(output_path)
        output_name = os.path.splitext(os.path.basename(output_path))[0]
        concat_list_path = os.path.join(output_dir, f"{output_name}_concat_list.txt")
        feasibility = self.videos_consistency_detect(input_files)

        if feasibility["consistency"] is True:
            _concat_list(input_files, concat_list_path)
            exe = ffmpeg(hide_banner=True)
            exe.f(concat=True).safe(0).input(concat_list_path).video_codec().audio_codec().output(output_path).run()
            os.remove(concat_list_path)
            self.print_log()
        else:
            self.log_error += "❌ 视频规格不同，无法进行合并。\n"
            print(feasibility)
            self.print_log()

    def print_log(self):
        run_log = "LOG\n"
        run_log += self.log_correct
        run_log += self.log_warning
        run_log += self.log_error
        print(run_log)
