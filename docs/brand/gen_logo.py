"""Sinh logo phẳng CineAI (SVG) — dải băng gấp 3 lần thành nút Play.

Chạy: python3 docs/brand/gen_logo.py -> docs/brand/logo.svg (có ô nền tối) và logo-mark.svg (chỉ biểu tượng, dùng trên nền tối).
Sau đó chép logo.svg sang frontend/public/{logo,favicon}.svg và admin/public/{logo,favicon}.svg.
"""
from pathlib import Path
OUT = Path(__file__).resolve().parent
import math
def inner_line(P,i,w):
    # cạnh i (P[i]->P[i+1]) dịch vào trong w
    a,b=P[i],P[(i+1)%3]; c=P[(i+2)%3]
    dx,dy=b[0]-a[0],b[1]-a[1]; L=math.hypot(dx,dy); nx,ny=-dy/L,dx/L
    if (c[0]-a[0])*nx+(c[1]-a[1])*ny<0: nx,ny=-nx,-ny
    return ((a[0]+nx*w,a[1]+ny*w),(b[0]+nx*w,b[1]+ny*w))
def outer_line(P,i): return (P[i],P[(i+1)%3])
def X(l1,l2):
    (x1,y1),(x2,y2)=l1; (x3,y3),(x4,y4)=l2
    d=(x1-x2)*(y3-y4)-(y1-y2)*(x3-x4)
    t=((x1-x3)*(y3-y4)-(y1-y3)*(x3-x4))/d
    return (x1+t*(x2-x1),y1+t*(y2-y1))
def f(pts): return " ".join(f"{x:.2f},{y:.2f}" for x,y in pts)
def mark(P,w,tones,sw):
    polys=[]
    for i in range(3):
        o,n=outer_line(P,i),inner_line(P,i,w)
        op,np_=outer_line(P,(i+2)%3),inner_line(P,(i+2)%3,w)   # cạnh trước
        on=outer_line(P,(i+1)%3)                               # cạnh sau
        polys.append([X(o,np_),P[(i+1)%3],X(n,on),X(n,np_)])
    return "\n  ".join(f'<polygon points="{f(p)}" fill="{t}" stroke="{t}" stroke-width="{sw}" stroke-linejoin="round"/>' for p,t in zip(polys,tones))
# thứ tự cạnh: 0 = trái (trên->dưới), 1 = dưới (trái->mũi), 2 = trên (mũi->trái)
TONES=("#C4F53A","#7CC61E","#E2FB93")
P=[(21,14),(21,50),(51,32)]
open(OUT/"logo.svg","w").write(f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" fill="none">
  <rect width="64" height="64" rx="14" fill="#0A0B0A"/>
  {mark(P,5.6,TONES,2.2)}
</svg>
''')
P2=[(3,3),(3,53),(47,28)]
open(OUT/"logo-mark.svg","w").write(f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 50 56" fill="none">
  {mark(P2,7.8,TONES,2.8)}
</svg>
''')
