# 结构化拆解字段

`source`：原视频 URL、视频 ID、文件绝对路径、采集时间、媒体时长/分辨率/帧率/音轨、采样策略与证据范围。

`characters[]`：稳定 ID、可见类型/物种、外形与饰物、首次/末次出现时间、可辨性限制。角色 ID 在同一视频的 scene 和逐秒表中一致。

`scenes[]`：编号、`start_s`、`end_s`、环境、在场角色、景别/机位/运镜、证据帧；`hard_cut_at_s` 只给经相邻帧核实的硬切。若全片单一连续 scene，仍填一条覆盖 `0.00～duration`，硬切列表为空。

`seconds[]`：每行覆盖 `[start_s,end_s)`，含 `scene_id`、`camera`、`framing`、`camera_motion`、`environment`、`evidence_frames`，并列出 `roles[]`：`id`、`screen_position`（左/中/右、前/中/后景，必要时估计百分比）、`body_pose_action`、`face_mouth`、`eyes_gaze`、`demeanor`、`emotion_inference`、`uncertainty`。同秒有多个角色时每个角色一条，不混写。不可判字段直写“不可判”。

时间统一保留两位小数展示，末段不足一秒时以真实片尾为 `end_s`。帧精度的切点按实际帧率换算；任何插值或模型推测均标明。音轨存在仅表明文件含音频，除非另行听取/转写，不描述具体声音。
