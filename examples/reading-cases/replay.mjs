import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const root = resolve(here, '../..');
const fixtures = JSON.parse(readFileSync(resolve(here, 'fixtures.json'), 'utf8'));
const { min, max, floor, ceil } = Math;
const calculations = {
  "1.3": (a, b, c, d) => [ceil(a/b)+1, a, (ceil(a/b)+1)*c+a*d],
  "1.6": (a, b, c, d) => [a+c, max(0,b-a-c), b-a-c-d],
  "2.3": (a, b, c, d) => [100*b/a, b-c, d+b-c],
  "2.6": (a, b, c, d) => [a+b*c, a, b*c*d],
  "3.3": (a, b, c, d) => [max(0,a-b-d), floor(max(0,a-b-d)/c), max(0,a-b-d)%c],
  "3.6": (a, b, c, d) => [b-c, (b-c<=a?b-c:0)*d, min(a,b-c)],
  "4.3": (a, b, c, d) => [100*a/(a+b), 100*a/(a+c), 100*(a+d)/(a+b+c+d)],
  "4.6": (a, b, c, d) => [100*(b+c+d)/(a+b+c+d), 100*d/(a+b+c+d), 100*(b+2*c+3*d)/(3*(a+b+c+d))],
  "5.3": (a, b, c, d) => [a-b-c, floor((a-b-c)/d), (a-b-c)%d],
  "5.6": (a, b, c, d) => [b+c-d, a-b-c+d, 100*(a-b-c+d)/a],
  "6.3": (a, b, c, d) => [a-b, max(0,a-b-c-d), max(0,200-max(0,a-b-c-d))],
  "6.6": (a, b, c, d) => [a*b*c, a*b*c*d, d*a*(b*c-1)],
  "7.3": (a, b, c, d) => [a+b+d, max(a,b)+d, c+max(a,b)+d],
  "7.6": (a, b, c, d) => [min(c,a-b), min(d,max(0,a-b-c)), max(0,c+d-(a-b))],
  "8.3": (a, b, c, d) => [a-b, floor(b/c)+1, max(0,a-b-d)],
  "8.6": (a, b, c, d) => [a-b, a-b-c, 100*d/(a-b-c)],
  "9.3": (a, b, c, d) => [a*b/100, a*b*c/10000, a*b*c/10000-d],
  "9.6": (a, b, c, d) => [a-b, 100-a+b, c+(a*d+(100-a+b)*600)/100],
  "10.3": (a, b, c, d) => [100*(c/100)**a, 100*(c/100)**a*(d/100)**b, 100*(1-(c/100)**a*(d/100)**b)],
  "10.6": (a, b, c, d) => [a*b, a*b*c/1000, a*d/1000],
};

function evaluate(fixtures,key,bits,calculations){
  const item=fixtures.lessons[key];
  if (!item || !/^[01]{4}$/.test(bits)) throw Error("Use a week from 1 to 10, a reading from 1 to 7, and four bits such as 0101.");
  const selected=Array.from(bits,Number);
  if(item.kind==="policy"){
    const observations=item.fields.map((field,i)=>fixtures.facts[field][selected[i]===1?1:2]);
    const rule=item.rules.find(([mask])=>Array.from(mask).every((v,i)=>v==="*"||v===bits[i]));
    if(!rule)throw Error("No matching rule in "+key);
    return {title:item.title,input:bits,observations,condition:rule[0],action:rule[1],reason:rule[2]};
  }
  const values=item.fields.map((field,i)=>field[selected[i]+1]);
  const answers=calculations[key](...values);
  return {title:item.title,input:bits,assumptions:item.assumptions,values:Object.fromEntries(item.fields.map((field,i)=>[field[0],values[i]])),
    metrics:item.metrics.map(([name,unit,formula],i)=>({name,unit,formula,value:answers[i]}))};
}

function readingLines(markdown) {
  let inFence = false;
  const prose = [];
  for (const raw of markdown.split('\n')) {
    const line = raw.trim();
    if (line.startsWith('```')) { inFence = !inFence; continue; }
    if (inFence || /^(#|[|<>]|[*-]{1,2}\s|\d+[.)、]\s|^\*\*样本|^\[)/.test(line)) continue;
    if ((line.match(/[\u3400-\u9fff]/g) || []).length < 10) continue;
    if (/[。？！？”]$/.test(line)) prose.push(line);
  }
  return prose;
}

function audit() {
  let passed = true;
  for (let week = 1; week <= 10; week++) {
    const folder = resolve(root, 'lessons', 'week-' + String(week).padStart(2,'0'));
    const paths = ['theory.md', ...Array.from({length:7}, (_,i) => 'readings/' + String(i+1).padStart(2,'0') + '.md')];
    const lines = new Set();
    for (const path of paths) {
      const article = readFileSync(resolve(folder,path),'utf8');
      for (const line of readingLines(article)) lines.add(line);
    }
    console.log('week ' + week + ': ' + lines.size + ' unique prose lines');
    if (lines.size < 2000) passed = false;
  }
  if (!passed) process.exitCode = 1;
}

const args = process.argv.slice(2);
if (args[0] === 'audit') {
  audit();
} else if (args.length === 3) {
  const output = evaluate(fixtures, Number(args[0])+'.'+Number(args[1]), args[2], calculations);
  console.log(JSON.stringify(output,null,2));
} else {
  console.error('Usage: node examples/reading-cases/replay.mjs <week> <reading> <four bits> | audit');
  process.exitCode = 2;
}
