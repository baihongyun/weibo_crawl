from docx import Document
from docx.shared import Inches

def save_to_docx(content_and_comment_dict):
    #如果没有内容和评论，直接返回
    if(len(content_and_comment_dict) < 0):
        return
    #将内容和评论直接写到文档中
    else:
        document = Document(docx = 'test.docx')
        for key in content_and_comment_dict:
             if key == "content":
                comment =  document.add_paragraph(content_and_comment_dict[key],style='List Bullet')
             elif key == "comment":
                  num_comment = len(content_and_comment_dict[key])
                  if num_comment > 0:
                        for content in content_and_comment_dict[key]:
                            document.add_paragraph( content)
             elif key == "url":
                pass
             else:
                pass
        document.save('test.docx')
#写封面
def write_cover(cover_dict):
    pass

if __name__ == "__main__":
    content = {'content':'微博内容','comment':['第一条评论','第二条评论','第三条评论']}
    save_to_docx(content)
