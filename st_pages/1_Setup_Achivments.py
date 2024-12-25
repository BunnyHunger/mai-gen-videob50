import streamlit as st
import os
import json
import subprocess
import traceback
from copy import deepcopy
from pre_gen import update_b50_data, st_init_cache_pathes
from pre_gen_int import update_b50_data_int
from gene_images import generate_single_image, check_mask_waring
from utils.PageUtils import *

def show_b50_dataframe(info_placeholder, user_id, data):
    with info_placeholder.container(border=True):
        st.write(f"{user_id}的B50数据预览: ")
        st.dataframe(data, column_order=["clip_id", "title", "level_label", "level",  "ds", "achievements", "fc", "fs", "ra", "dxScore"])

st.header("Step 1: 配置生成器参数和B50成绩数据")

def check_username(input_username):
    # 检查用户名是否包含非法字符
    if any(char in input_username for char in ['/', '\\', ':', '*', '?', '"', '<', '>', '|']):
        return remove_invalid_chars(input_username), input_username
    else:
        return input_username, input_username


with st.container(border=True):
    G_config = read_global_config()
    raw_username = G_config.get('USER_ID_RAW', '')
    input_username = st.text_input("输入水鱼查分器用户名（国服查询）或一个您喜欢的用户名（国际服）", value=raw_username)

    if st.button("确定"):
        if not input_username:
            st.error("用户名不能为空！")
            st.session_state.config_saved = False
        else:  
            # 输入的username可能作为文件路径，需要去除非法字符
            # raw_username作为发送给查分器的用户名，除非用户名中包含非法字符，否则与username相同
            username, raw_username = check_username(input_username)
            # 更新配置字典
            G_config['USER_ID'] = username
            G_config['USER_ID_RAW'] = raw_username
            # 写入配置文件
            write_global_config(G_config)
            st.success("配置已保存！")
            st.session_state.config_saved = True  # 添加状态标记

def st_generate_b50_images(placeholder, user_id):
    b50_data_file = os.path.join(os.path.dirname(__file__), '..', 'b50_datas', f"b50_config_{user_id}.json")
    # read b50_data
    b50_data = load_config(b50_data_file)
    # make folder for user's b50_images
    os.makedirs(f"./b50_images/{user_id}", exist_ok=True)
    with placeholder.container(border=True):
        pb = st.progress(0, text="正在生成B50成绩背景图片...")
        mask_check_cnt = 0
        mask_warn = False
        warned = False
        for index, record_detail in enumerate(b50_data):
            pb.progress((index + 1) / len(b50_data), text=f"正在生成B50成绩背景图片({index + 1}/{len(b50_data)})")
            acc_string = f"{record_detail['achievements']:.4f}"
            mask_check_cnt, mask_warn = check_mask_waring(acc_string, mask_check_cnt, mask_warn)
            if mask_warn and not warned:
                st.warning("检测到多个仅有一位小数精度的成绩，请尝试取消查分器设置的成绩掩码以获取精确成绩。特殊情况请忽略。")
                warned = True
            record_for_gene_image = deepcopy(record_detail)
            record_for_gene_image['achievements'] = acc_string
            prefix = "PastBest" if index < 35 else "NewBest"
            image_name_index = index if index < 35 else index - 35
            generate_single_image(
                "./images/B50ViedoBase.png",
                record_for_gene_image,
                user_id,
                prefix,
                image_name_index,
            )

def update_b50(placeholder, update_function, b50_raw_file, b50_data_file, username, replace_b50_data=False): 
    try:
        if replace_b50_data:
            b50_data = update_function(b50_raw_file, b50_data_file, username)
            st.success("已更新B50数据！")
            st.session_state.data_updated_step1 = True
        else:
            b50_data = load_config(b50_data_file)
            st.success("已加载缓存的B50数据")
            st.session_state.data_updated_step1 = True
        show_b50_dataframe(placeholder, username, b50_data)
    except Exception as e:
        st.session_state.data_updated_step1 = False
        st.error(f"获取B50数据时发生错误: {e}")
        st.error(traceback.format_exc())

# 仅在配置已保存时显示"开始预生成"按钮
if st.session_state.get('config_saved', False):
    G_config = read_global_config()
    username = G_config.get('USER_ID', '')
    raw_username = G_config.get('USER_ID_RAW', '')
    image_path = f"./b50_images/{username}"

    st_init_cache_pathes()

    b50_raw_file = f"./b50_datas/b50_raw_{username}.json"
    b50_data_file = f"./b50_datas/b50_config_{username}.json"
    config_output_file = f"./b50_datas/video_configs_{username}.json"
    b50_data = None

    if 'data_updated_step1' not in st.session_state:
        st.session_state.data_updated_step1 = False

    if os.path.exists(b50_data_file):
        st.warning("检测到用户已缓存有B50数据，是否确认获取最新的数据？这将会覆盖当前已有数据。")
        options = ["使用缓存数据（无视服务器）", "更新并替换当前数据"]
        replace_confirm = st.radio("请选择", options, index=0)
        replace_b50_data = replace_confirm == options[1]
    else:
        replace_b50_data = True
    
    update_info_placeholder = st.empty()

    if st.button("从水鱼获取B50数据（国服）"):
        with st.spinner("正在获取B50数据更新..."):
            update_b50(update_info_placeholder, update_b50_data, b50_raw_file, b50_data_file, raw_username, replace_b50_data=replace_b50_data)

    @st.dialog("从HTML源码导入数据")
    def input_html_data():
        st.info("请将复制的网页源代码粘贴到下方输入栏：")
        if os.path.exists(f"./{username}.html"):
            st.info(f"注意，重复导入将会覆盖已有html数据文件：{username}.html")
        html_input = st.text_area("html_input", height=600)
        if st.button("确认保存"):
            with open(f"./{username}.html", 'w', encoding="utf-8") as f:
               f.write(html_input)
            st.toast("HTML数据已保存！")
            st.rerun()

    with st.container(border=True):
        st.info("如您使用国际服数据，请先点击下方左侧按钮导入源代码，再使用下方右侧按钮读取数据。国服用户请跳过。")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("导入B50数据源代码"):
                # 参考水鱼做法使用dialog框架
                input_html_data()
        
        with col2:
            if st.button("从本地HTML读取B50（国际服）"):
                with st.spinner("正在读取HTML数据..."):
                    update_b50(update_info_placeholder, update_b50_data_int, b50_raw_file, b50_data_file, username, replace_b50_data=replace_b50_data)



    if st.session_state.get('data_updated_step1', False):
        with st.container(border=True):
            st.write("确认你的B50数据无误后，请点击下面的按钮，生成成绩背景图片：")
            if st.button("生成成绩背景图片"):
                generate_info_placeholder = st.empty()
                try:
                    st_generate_b50_images(generate_info_placeholder, username)
                    st.success("生成成绩背景图片完成！")
                except Exception as e:
                    st.error(f"生成成绩背景图片时发生错误: {e}")
                    st.error(traceback.format_exc())
            if os.path.exists(image_path):
                absolute_path = os.path.abspath(image_path)
            else:
                absolute_path = os.path.abspath(os.path.dirname(image_path))
            if st.button("打开成绩图片文件夹", key=f"open_folder_{username}"):
                open_file_explorer(absolute_path)
            st.info("如果你已经生成过背景图片，且无需更新，可以跳过，请点击进行下一步按钮。")
            if st.button("进行下一步"):
                st.switch_page("st_pages/2_Search_For_Videoes.py")

else:
    st.warning("请先确定配置！")  # 如果未保存配置，给出提示