#!/usr/bin/env python3
"""Generate editable IDEF0 draw.io pages, SVG exports and PlantUML ER source."""
from pathlib import Path
from xml.etree import ElementTree as ET
import argparse
import html
import json
import textwrap

ROOT = Path(__file__).resolve().parents[1]
W, H = 1800, 1200
ROLES = {'I':'Входы', 'O':'Выходы', 'C':'Управление', 'M':'Механизмы'}

class Canvas:
    def __init__(self, name):
        self.svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
            '<defs><marker id="arrow" markerWidth="12" markerHeight="12" refX="9" refY="5" orient="auto" markerUnits="userSpaceOnUse"><path d="M0 0 L10 5 L0 10 Z" fill="#222"/></marker></defs>',
            '<rect width="100%" height="100%" fill="white"/>']
        self.diagram = ET.Element('diagram', id=name, name=name)
        model = ET.SubElement(self.diagram,'mxGraphModel', dx=str(W),dy=str(H),grid='1',gridSize='10',guides='1',tooltips='1',connect='1',arrows='1',fold='1',page='1',pageScale='1',pageWidth=str(W),pageHeight=str(H),math='0',shadow='0')
        self.root=ET.SubElement(model,'root')
        ET.SubElement(self.root,'mxCell',id='0')
        ET.SubElement(self.root,'mxCell',id='1',parent='0')
        self.serial=0
        self.labels=[]

    def identity(self):
        self.serial+=1
        return f'item-{self.serial}'

    def text(self,x,y,value,size=25,bold=False,width=None,anchor='start'):
        lines = textwrap.wrap(value, width=width, break_long_words=False, break_on_hyphens=False) if width else value.split('\n')
        for i,line in enumerate(lines):
            self.svg.append(f'<text x="{x}" y="{y+i*(size+5)}" fill="#181818" font-family="DejaVu Sans, Arial, sans-serif" font-size="{size}" font-weight="{"bold" if bold else "normal"}" text-anchor="{anchor}">{html.escape(line)}</text>')
        visual_width=(width or max(map(len,lines),default=1))*size*.56
        start_x=x if anchor=='start' else x-visual_width/2 if anchor=='middle' else x-visual_width
        cell=ET.SubElement(self.root,'mxCell', id=self.identity(),value='\n'.join(lines),style=f'text;html=0;whiteSpace=wrap;align={"left" if anchor=="start" else "center" if anchor=="middle" else "right"};verticalAlign=top;fontFamily=DejaVu Sans;fontSize={size};fontColor=#181818;fontStyle={1 if bold else 0};',vertex='1',parent='1')
        ET.SubElement(cell,'mxGeometry',x=str(start_x),y=str(y-size),width=str(visual_width+8),height=str(len(lines)*(size+5)+8),attrib={'as':'geometry'})
        return len(lines)*(size+5)

    def box(self,x,y,w,h,name,number):
        self.svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="#f7f8f9" stroke="#222" stroke-width="2.5"/>')
        lines=textwrap.wrap(name,width=15,break_long_words=False)
        first_y=y+(h-len(lines)*29)/2+22
        for i,line in enumerate(lines):
            self.svg.append(f'<text x="{x+w/2}" y="{first_y+i*29}" font-family="DejaVu Sans, Arial, sans-serif" font-size="23" text-anchor="middle" fill="#111">{html.escape(line)}</text>')
        cell=ET.SubElement(self.root,'mxCell',id=self.identity(),value=name,style='rounded=0;whiteSpace=wrap;html=0;fillColor=#f7f8f9;strokeColor=#222222;strokeWidth=2;fontSize=23;fontFamily=DejaVu Sans;align=center;',vertex='1',parent='1')
        ET.SubElement(cell,'mxGeometry',x=str(x),y=str(y),width=str(w),height=str(h),attrib={'as':'geometry'})
        self.text(x+w-14,y+h-12,str(number),22,anchor='end')

    def arrow(self,points,label='',label_position=None,arrow=True):
        pairs=' '.join(f'{x},{y}' for x,y in points)
        # White underlay makes crossings distinguishable from explicit branch junctions.
        self.svg.append(f'<polyline points="{pairs}" fill="none" stroke="white" stroke-width="7"/>')
        self.svg.append(f'<polyline points="{pairs}" fill="none" stroke="#222" stroke-width="2.4"'+(' marker-end="url(#arrow)"' if arrow else '')+'/>')
        cell=ET.SubElement(self.root,'mxCell',id=self.identity(),value='',style='edgeStyle=none;html=0;rounded=0;endArrow=block;endFill=1;endSize=10;strokeColor=#222222;strokeWidth=2;'+('' if arrow else 'endArrow=none;'),edge='1',parent='1')
        geometry=ET.SubElement(cell,'mxGeometry',relative='1',attrib={'as':'geometry'})
        ET.SubElement(geometry,'mxPoint',x=str(points[0][0]),y=str(points[0][1]),attrib={'as':'sourcePoint'})
        ET.SubElement(geometry,'mxPoint',x=str(points[-1][0]),y=str(points[-1][1]),attrib={'as':'targetPoint'})
        if len(points)>2:
            array=ET.SubElement(geometry,'Array',attrib={'as':'points'})
            for x,y in points[1:-1]:
                ET.SubElement(array,'mxPoint',x=str(x),y=str(y))
        if label:
            x,y=label_position or points[0]
            self.labels.append((x,y,label))

    def dot(self,x,y):
        self.svg.append(f'<circle cx="{x}" cy="{y}" r="4.5" fill="#222"/>')
        cell=ET.SubElement(self.root,'mxCell',id=self.identity(),value='',style='ellipse;fillColor=#222222;strokeColor=none;',vertex='1',parent='1')
        ET.SubElement(cell,'mxGeometry',x=str(x-4.5),y=str(y-4.5),width='9',height='9',attrib={'as':'geometry'})

    def legend(self,interface,flows):
        y=150
        for role in 'IOCM':
            self.text(1285,y,ROLES[role],25,True);y+=37
            for code,label in interface[role].items():
                y+=self.text(1290,y,f'{code}  {label}',22,width=39)+9
            y+=8
        if flows:
            self.text(1285,y,'Внутренние связи',25,True);y+=36
            for flow in flows:
                y+=self.text(1290,y,f'{flow["id"]}  {flow["label"]}',22,width=39)+9
        if y>1160:
            raise ValueError(f'Legend overflow: {y}')

    def finish(self):
        for x,y,label in self.labels:
            self.svg.append(f'<rect x="{x-3}" y="{y-25}" width="{max(32,len(label)*15)}" height="31" fill="white"/>')
            self.text(x,y,label,24,True)
        self.svg.append('</svg>')
        return '\n'.join(self.svg)+'\n'

def header(canvas,node,title):
    canvas.text(65,55,f'{node}  {title}',32,True)
    canvas.text(65,95,'IDEF0  Библиотечное обслуживание',23)
    canvas.text(65,1174,'I — слева   C — сверху   O — справа   M — снизу   • — ветвление стрелки',23)
    canvas.text(1190,1140,'Узел '+node,23,anchor='end')

def context_page(model):
    context=model['context'];c=Canvas('A-0');header(c,'A-0',context['title'])
    x,y,w,h=440,420,480,250
    c.box(x,y,w,h,context['title'],0)
    for i,code in enumerate(context['interface']['I']):
        yy=y+30+i*45
        c.arrow([(90,yy),(x,yy)],code,(105,yy-15))
    for i,code in enumerate(context['interface']['O']):
        yy=y+40+i*55
        c.arrow([(x+w,yy),(1190,yy)],code,(1130,yy-15))
    for i,code in enumerate(context['interface']['C']):
        xx=x+100+i*140
        c.arrow([(xx,190),(xx,y)],code,(xx+10,220))
    for i,code in enumerate(context['interface']['M']):
        xx=x+100+i*140
        c.arrow([(xx,1030),(xx,y+h)],code,(xx+10,995))
    c.text(90,750,'Цель модели',25,True)
    c.text(90,790,model['purpose'],23,width=27)
    c.text(90,950,'Точка зрения',25,True)
    c.text(90,990,model['viewpoint'],23,width=27)
    c.legend(context['interface'],[])
    return c

def decomposition_page(spec):
    c=Canvas(spec['node']);header(c,spec['node'],spec['title'])
    n=len(spec['children']);w,h=(225 if n==4 else 245),125
    coords=([(215+i*240,285+i*180) for i in range(4)] if n==4 else
            [(245+i*335,300+i*255) for i in range(3)])
    boxes={item['id']:(x,y,w,h) for item,(x,y) in zip(spec['children'],coords)}
    output_keys={child:[] for child in boxes}
    input_keys={child:[] for child in boxes}
    for role,destination in [('O',output_keys),('I',input_keys)]:
        for code in spec['interface'][role]:
            for child in spec['boundary'][code]:destination[child].append(code)
    for flow in spec['flows']:
        output_keys[flow['from']].append(flow['id'])
        if flow['role']=='I':input_keys[flow['to']].append(flow['id'])
    def port_y(child,key,keys):
        x,y,ww,hh=boxes[child]
        return y+hh*(keys[child].index(key)+1)/(len(keys[child])+1)
    # Arrow rails are separate. Shared arrows have explicit junction dots.
    for role in 'CM':
        for i,code in enumerate(spec['interface'][role]):
            children=spec['boundary'][code]
            points=[]
            for child in children:
                x,y,ww,hh=boxes[child]
                offset=35+i*55
                points.append((x+offset,y if role=='C' else y+hh))
            rail_y=170+i*35 if role=='C' else 1060-i*30
            start=(points[0][0],130 if role=='C' else 1100)
            c.arrow([start,(start[0],rail_y),(points[-1][0],rail_y)],arrow=False)
            c.text(start[0]+8,start[1]+28 if role=='C' else start[1]-10,code,24,True)
            for xx,yy in points:
                c.arrow([(xx,rail_y),(xx,yy)])
                if len(points)>1:c.dot(xx,rail_y)
    for i,(code,label) in enumerate(spec['interface']['I'].items()):
        targets=spec['boundary'][code]
        boundary_y=300+i*125
        rail_x=150+i*12
        c.arrow([(90,boundary_y),(rail_x,boundary_y)],code,(95,boundary_y-15),arrow=False)
        for j,child in enumerate(targets):
            x,y,ww,hh=boxes[child]
            yy=port_y(child,code,input_keys)
            c.arrow([(rail_x,boundary_y),(rail_x,yy),(x,yy)])
    for i,(code,label) in enumerate(spec['interface']['O'].items()):
        sources=spec['boundary'][code]
        if len(sources)==1:
            x,y,ww,hh=boxes[sources[0]]
            yy=port_y(sources[0],code,output_keys)
            c.arrow([(x+ww,yy),(1195,yy)],code,(1200,yy-15))
        else:
            # A composite output merges the reader card and reservation document.
            rail_x=1180;end_y=360
            for j,child in enumerate(sources):
                x,y,ww,hh=boxes[child];yy=port_y(child,code,output_keys)
                c.arrow([(x+ww,yy),(rail_x,yy),(rail_x,end_y)],arrow=False)
            c.dot(rail_x,end_y)
            c.arrow([(rail_x,end_y),(1195,end_y)],code,(1200,end_y-15))
    incoming={};outgoing={}
    for i,flow in enumerate(spec['flows']):
        source,target=flow['from'],flow['to']
        sx,sy,sw,sh=boxes[source];tx,ty,tw,th=boxes[target]
        si=outgoing.get(source,0);outgoing[source]=si+1
        ti=incoming.get(target,0);incoming[target]=ti+1
        source_y=port_y(source,flow['id'],output_keys)
        if ty>sy:
            if flow['role']=='I':
                target_y=port_y(target,flow['id'],input_keys)
                rail_x=tx-10-ti*5
                points=[(sx+sw,source_y),(rail_x,source_y),(rail_x,target_y),(tx,target_y)]
                label_position=((sx+sw+rail_x)/2,source_y-15)
            else:
                target_x=tx+120+ti*30
                points=[(sx+sw,source_y),(target_x,source_y),(target_x,ty)]
                label_position=((sx+sw+target_x)/2,source_y-15)
        elif flow['role']=='C':
            # Feedback debt controls the next service request.
            target_x=tx+175
            points=[(sx+sw,source_y),(1215,source_y),(1215,135),(target_x,135),(target_x,ty)]
            label_position=(1100,126)
        else:
            target_y=port_y(target,flow['id'],input_keys)
            rail_x=tx-15
            points=[(sx+sw,source_y),(1228,source_y),(1228,1090),(rail_x,1090),(rail_x,target_y),(tx,target_y)]
            label_position=(1060,1080)
        c.arrow(points,flow['id'],label_position)
    # Boxes are drawn last so internal connectors cannot obscure function names.
    for i,item in enumerate(spec['children'],1):
        c.box(*boxes[item['id']],item['name'],i)
        x,y,ww,hh=boxes[item['id']]
        c.text(x+3,y+hh+27,item['id'],22)
    c.legend(spec['interface'],spec['flows'])
    return c

def plantuml_source(model):
    lines=['@startuml library_er','!pragma layout smetana','left to right direction',
        'hide circle','skinparam backgroundColor white','skinparam shadowing false',
        'skinparam linetype ortho','skinparam classFontName DejaVu Sans','skinparam classFontSize 18',
        'skinparam classAttributeFontSize 16','skinparam ArrowFontName DejaVu Sans','skinparam ArrowFontSize 16',
        'skinparam classBackgroundColor #F6F7F9','skinparam classBorderColor #333333',
        'skinparam ArrowColor #333333','skinparam nodesep 45','skinparam ranksep 65',
        'title','ER модель библиотечного обслуживания','16 сущностей и 19 связей','end title','']
    for entity in model['entities']:
        lines.append(f'entity "{entity["name"]}\\n{entity["title"]}" as {entity["name"]} {{')
        business={'Author':['FullName'],'Publisher':['Name'],'Category':['Name'],'Book':['Title','Isbn'],
            'Branch':['Name'],'StorageLocation':['ShelfCode'],'BookCopy':['InventoryNumber'],
            'Reader':['CardNumber','Status'],'Employee':['FullName','Role'],'Reservation':['Status'],
            'Loan':['IssuedAt'],'LoanItem':['DueAt'],'Fine':['AmountCents'],'Payment':['AmountCents']}
        for attr in entity['attributes']:
            if not attr['key'] and attr['name'] not in business.get(entity['name'],[]):continue
            prefix='* ' if not attr['nullable'] else '  '
            suffix=' '+('<<'+attr['key']+'>>') if attr['key'] else ''
            lines.append(f'  {prefix}{attr["name"]}{suffix}')
        lines.extend(['}',''])
    for r in model['relations']:
        role={'IssuedByEmployeeId':'выдал','ReturnedByEmployeeId':'принял возврат','ReceivedByEmployeeId':'учёл оплату'}.get(r['foreign_key'])
        lines.append(f'{r["parent"]} "{r["parent_cardinality"]}" -- "{r["child_cardinality"]}" {r["child"]}'+(' : '+role if role else ''))
    lines.extend(['', 'legend bottom',
        'PK — первичный ключ    FK — внешний ключ    UQ — уникальность',
        '* — обязательный атрибут    0..1 — необязательная связь    0..* — любое число',
        'Loan содержит 1..* LoanItem по бизнес правилу завершённой выдачи',
        'BookCopy имеет 0..* позиций за историю и не более 1 активной позиции',
        'endlegend','@enduml',''])
    return '\n'.join(lines)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'diagrams')
    args=parser.parse_args()
    model=json.loads((ROOT/'model/idef0.json').read_text(encoding='utf-8'))
    entities=json.loads((ROOT/'model/entities.json').read_text(encoding='utf-8'))
    canvases=[context_page(model)]+[decomposition_page(x) for x in model['diagrams']]
    idef=args.output/'idef0';idef.mkdir(parents=True,exist_ok=True)
    mxfile=ET.Element('mxfile',host='app.diagrams.net',type='device',version='29.0.0')
    for canvas in canvases:
        name=canvas.diagram.attrib['name']
        (idef/(name+'.svg')).write_text(canvas.finish(),encoding='utf-8',newline='\n')
        mxfile.append(canvas.diagram)
    ET.indent(mxfile,space='  ')
    ET.ElementTree(mxfile).write(idef/'library_idef0.drawio',encoding='utf-8',xml_declaration=True)
    er=args.output/'er';er.mkdir(parents=True,exist_ok=True)
    (er/'library_er.puml').write_text(plantuml_source(entities),encoding='utf-8',newline='\n')
    print('Generated 6 IDEF0 SVG files, 6 editable draw.io pages and PlantUML ER source')

if __name__=='__main__':main()
