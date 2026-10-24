/**
 * 智能节点地理位置与国家/区域解析器
 * 支持：国旗 Emoji、中文/英文地名正则匹配、Cloudflare Anycast CDN 识别、
 * 以及异步 IP/域名 GeoIP 归属地解析与多级缓存
 */

// 1. 常见国旗 Emoji 到国家信息的映射
export const EMOJI_FLAG_MAP = {
  '🇭🇰': { code: 'HK', flag: '🇭🇰', text: '香港' },
  '🇹🇼': { code: 'TW', flag: '🇹🇼', text: '台湾' },
  '🇯🇵': { code: 'JP', flag: '🇯🇵', text: '日本' },
  '🇸🇬': { code: 'SG', flag: '🇸🇬', text: '新加坡' },
  '🇺🇸': { code: 'US', flag: '🇺🇸', text: '美国' },
  '🇰🇷': { code: 'KR', flag: '🇰🇷', text: '韩国' },
  '🇬🇧': { code: 'GB', flag: '🇬🇧', text: '英国' },
  '🇩🇪': { code: 'DE', flag: '🇩🇪', text: '德国' },
  '🇫🇷': { code: 'FR', flag: '🇫🇷', text: '法国' },
  '🇨🇦': { code: 'CA', flag: '🇨🇦', text: '加拿大' },
  '🇦🇺': { code: 'AU', flag: '🇦🇺', text: '澳大利亚' },
  '🇷🇺': { code: 'RU', flag: '🇷🇺', text: '俄罗斯' },
  '🇮🇳': { code: 'IN', flag: '🇮🇳', text: '印度' },
  '🇹🇭': { code: 'TH', flag: '🇹🇭', text: '泰国' },
  '🇻🇳': { code: 'VN', flag: '🇻🇳', text: '越南' },
  '🇵🇭': { code: 'PH', flag: '🇵🇭', text: '菲律宾' },
  '🇲🇾': { code: 'MY', flag: '🇲🇾', text: '马来西亚' },
  '🇳🇱': { code: 'NL', flag: '🇳🇱', text: '荷兰' },
  '🇹🇷': { code: 'TR', flag: '🇹🇷', text: '土耳其' },
  '🇦🇷': { code: 'AR', flag: '🇦🇷', text: '阿根廷' },
  '🇧🇷': { code: 'BR', flag: '🇧🇷', text: '巴西' },
  '🇲🇽': { code: 'MX', flag: '🇲🇽', text: '墨西哥' },
  '🇮🇩': { code: 'ID', flag: '🇮🇩', text: '印尼' },
  '🇨🇭': { code: 'CH', flag: '🇨🇭', text: '瑞士' },
  '🇸🇪': { code: 'SE', flag: '🇸🇪', text: '瑞典' },
  '🇳🇴': { code: 'NO', flag: '🇳🇴', text: '挪威' },
  '🇫🇮': { code: 'FI', flag: '🇫🇮', text: '芬兰' },
  '🇮🇪': { code: 'IE', flag: '🇮🇪', text: '爱尔兰' },
  '🇮🇹': { code: 'IT', flag: '🇮🇹', text: '意大利' },
  '🇪🇸': { code: 'ES', flag: '🇪🇸', text: '西班牙' },
  '🇵🇹': { code: 'PT', flag: '🇵🇹', text: '葡萄牙' },
  '🇿🇦': { code: 'ZA', flag: '🇿🇦', text: '南非' },
  '🇦🇪': { code: 'AE', flag: '🇦🇪', text: '阿联酋' },
  '🇨🇳': { code: 'CN', flag: '🇨🇳', text: '中国' }
}

// 2. 节点名称与地域代号精准规则列表
export const LOCATION_RULES = [
  // 香港
  {
    code: 'HK',
    flag: '🇭🇰',
    text: '香港',
    regex: /(?:^|[^a-zA-Z])(?:HK|HKG|Hong\s*Kong)(?:[^a-zA-Z]|$)|香港|深港|广港|沪港/i
  },
  // 台湾
  {
    code: 'TW',
    flag: '🇹🇼',
    text: '台湾',
    regex: /(?:^|[^a-zA-Z])(?:TW|TWN|Taiwan|Taipei)(?:[^a-zA-Z]|$)|台湾|台北|台中|高雄|深台/i
  },
  // 日本
  {
    code: 'JP',
    flag: '🇯🇵',
    text: '日本',
    regex: /(?:^|[^a-zA-Z])(?:JP|JPN|Japan|Tokyo|Osaka)(?:[^a-zA-Z]|$)|日本|东京|大阪|川崎|沪日|京日/i
  },
  // 新加坡
  {
    code: 'SG',
    flag: '🇸🇬',
    text: '新加坡',
    regex: /(?:^|[^a-zA-Z])(?:SG|SGP|Singapore)(?:[^a-zA-Z]|$)|新加坡|狮城|沪新|广新/i
  },
  // 美国
  {
    code: 'US',
    flag: '🇺🇸',
    text: '美国',
    regex: /(?:^|[^a-zA-Z])(?:US|USA|United\s*States|America|Los\s*Angeles|San\s*Jose|Seattle|Chicago|Dallas|New\s*York|Phoenix|Miami|Portland|Oregon|Virginia|Atlanta|Silicon\s*Valley)(?:[^a-zA-Z]|$)|美国|洛杉矶|硅谷|圣何塞|西雅图|芝加哥|达拉斯|纽约|波特兰|俄勒冈|凤凰城|弗吉尼亚|迈阿密|亚特兰大|沪美|中美/i
  },
  // 韩国
  {
    code: 'KR',
    flag: '🇰🇷',
    text: '韩国',
    regex: /(?:^|[^a-zA-Z])(?:KR|KOR|Korea|Seoul)(?:[^a-zA-Z]|$)|韩国|首尔|仁川/i
  },
  // 英国
  {
    code: 'GB',
    flag: '🇬🇧',
    text: '英国',
    regex: /(?:^|[^a-zA-Z])(?:UK|GB|GBR|United\s*Kingdom|Great\s*Britain|London)(?:[^a-zA-Z]|$)|英国|伦敦/i
  },
  // 德国
  {
    code: 'DE',
    flag: '🇩🇪',
    text: '德国',
    regex: /(?:^|[^a-zA-Z])(?:DE|DEU|Germany|Frankfurt|Berlin)(?:[^a-zA-Z]|$)|德国|法兰克福|柏林|京德/i
  },
  // 法国
  {
    code: 'FR',
    flag: '🇫🇷',
    text: '法国',
    regex: /(?:^|[^a-zA-Z])(?:FR|FRA|France|Paris)(?:[^a-zA-Z]|$)|法国|巴黎/i
  },
  // 加拿大
  {
    code: 'CA',
    flag: '🇨🇦',
    text: '加拿大',
    regex: /(?:^|[^a-zA-Z])(?:CA|CAN|Canada|Toronto|Vancouver)(?:[^a-zA-Z]|$)|加拿大|多伦多|温哥华/i
  },
  // 澳大利亚
  {
    code: 'AU',
    flag: '🇦🇺',
    text: '澳大利亚',
    regex: /(?:^|[^a-zA-Z])(?:AU|AUS|Australia|Sydney|Melbourne)(?:[^a-zA-Z]|$)|澳大利亚|澳洲|悉尼|墨尔本/i
  },
  // 俄罗斯
  {
    code: 'RU',
    flag: '🇷🇺',
    text: '俄罗斯',
    regex: /(?:^|[^a-zA-Z])(?:RU|RUS|Russia|Moscow)(?:[^a-zA-Z]|$)|俄罗斯|莫斯科|圣彼得堡/i
  },
  // 印度
  {
    code: 'IN',
    flag: '🇮🇳',
    text: '印度',
    regex: /(?:^|[^a-zA-Z])(?:IN|IND|India|Mumbai|Delhi)(?:[^a-zA-Z]|$)|印度|孟买|新德里/i
  },
  // 泰国
  {
    code: 'TH',
    flag: '🇹🇭',
    text: '泰国',
    regex: /(?:^|[^a-zA-Z])(?:TH|THA|Thailand|Bangkok)(?:[^a-zA-Z]|$)|泰国|曼谷/i
  },
  // 越南
  {
    code: 'VN',
    flag: '🇻🇳',
    text: '越南',
    regex: /(?:^|[^a-zA-Z])(?:VN|VNM|Vietnam|Hanoi|Ho\s*Chi\s*Minh)(?:[^a-zA-Z]|$)|越南|河内|胡志明/i
  },
  // 菲律宾
  {
    code: 'PH',
    flag: '🇵🇭',
    text: '菲律宾',
    regex: /(?:^|[^a-zA-Z])(?:PH|PHL|Philippines|Manila)(?:[^a-zA-Z]|$)|菲律宾|马尼拉/i
  },
  // 马来西亚
  {
    code: 'MY',
    flag: '🇲🇾',
    text: '马来西亚',
    regex: /(?:^|[^a-zA-Z])(?:MY|MYS|Malaysia|Kuala\s*Lumpur)(?:[^a-zA-Z]|$)|马来西亚|吉隆坡|大马/i
  },
  // 荷兰
  {
    code: 'NL',
    flag: '🇳🇱',
    text: '荷兰',
    regex: /(?:^|[^a-zA-Z])(?:NL|NLD|Netherlands|Amsterdam)(?:[^a-zA-Z]|$)|荷兰|阿姆斯特丹/i
  },
  // 土耳其
  {
    code: 'TR',
    flag: '🇹🇷',
    text: '土耳其',
    regex: /(?:^|[^a-zA-Z])(?:TR|TUR|Turkey|Istanbul)(?:[^a-zA-Z]|$)|土耳其|伊斯坦布尔/i
  },
  // 阿根廷
  {
    code: 'AR',
    flag: '🇦🇷',
    text: '阿根廷',
    regex: /(?:^|[^a-zA-Z])(?:AR|ARG|Argentina)(?:[^a-zA-Z]|$)|阿根廷/i
  },
  // 巴西
  {
    code: 'BR',
    flag: '🇧🇷',
    text: '巴西',
    regex: /(?:^|[^a-zA-Z])(?:BR|BRA|Brazil|Sao\s*Paulo)(?:[^a-zA-Z]|$)|巴西|圣保罗/i
  },
  // 墨西哥
  {
    code: 'MX',
    flag: '🇲🇽',
    text: '墨西哥',
    regex: /(?:^|[^a-zA-Z])(?:MX|MEX|Mexico)(?:[^a-zA-Z]|$)|墨西哥/i
  },
  // 印尼
  {
    code: 'ID',
    flag: '🇮🇩',
    text: '印尼',
    regex: /(?:^|[^a-zA-Z])(?:ID|IDN|Indonesia|Jakarta)(?:[^a-zA-Z]|$)|印尼|印度尼西亚|雅加达/i
  },
  // 瑞士
  {
    code: 'CH',
    flag: '🇨🇭',
    text: '瑞士',
    regex: /(?:^|[^a-zA-Z])(?:CH|CHE|Switzerland|Zurich|Geneva)(?:[^a-zA-Z]|$)|瑞士|苏黎世|日内瓦/i
  },
  // 瑞典
  {
    code: 'SE',
    flag: '🇸🇪',
    text: '瑞典',
    regex: /(?:^|[^a-zA-Z])(?:SE|SWE|Sweden|Stockholm)(?:[^a-zA-Z]|$)|瑞典|斯德哥尔摩/i
  },
  // 挪威
  {
    code: 'NO',
    flag: '🇳🇴',
    text: '挪威',
    regex: /(?:^|[^a-zA-Z])(?:NO|NOR|Norway|Oslo)(?:[^a-zA-Z]|$)|挪威|奥斯陆/i
  },
  // 芬兰
  {
    code: 'FI',
    flag: '🇫🇮',
    text: '芬兰',
    regex: /(?:^|[^a-zA-Z])(?:FI|FIN|Finland|Helsinki)(?:[^a-zA-Z]|$)|芬兰|赫尔辛基/i
  },
  // 爱尔兰
  {
    code: 'IE',
    flag: '🇮🇪',
    text: '爱尔兰',
    regex: /(?:^|[^a-zA-Z])(?:IE|IRL|Ireland|Dublin)(?:[^a-zA-Z]|$)|爱尔兰|都柏林/i
  },
  // 意大利
  {
    code: 'IT',
    flag: '🇮🇹',
    text: '意大利',
    regex: /(?:^|[^a-zA-Z])(?:IT|ITA|Italy|Rome|Milan)(?:[^a-zA-Z]|$)|意大利|罗马|米兰/i
  },
  // 西班牙
  {
    code: 'ES',
    flag: '🇪🇸',
    text: '西班牙',
    regex: /(?:^|[^a-zA-Z])(?:ES|ESP|Spain|Madrid|Barcelona)(?:[^a-zA-Z]|$)|西班牙|马德里|巴塞罗那/i
  },
  // 葡萄牙
  {
    code: 'PT',
    flag: '🇵🇹',
    text: '葡萄牙',
    regex: /(?:^|[^a-zA-Z])(?:PT|PRT|Portugal|Lisbon)(?:[^a-zA-Z]|$)|葡萄牙|里斯本/i
  },
  // 南非
  {
    code: 'ZA',
    flag: '🇿🇦',
    text: '南非',
    regex: /(?:^|[^a-zA-Z])(?:ZA|ZAF|South\s*Africa|Johannesburg)(?:[^a-zA-Z]|$)|南非|约翰内斯堡/i
  },
  // 阿联酋
  {
    code: 'AE',
    flag: '🇦🇪',
    text: '阿联酋',
    regex: /(?:^|[^a-zA-Z])(?:AE|ARE|UAE|United\s*Arab\s*Emirates|Dubai)(?:[^a-zA-Z]|$)|阿联酋|迪拜/i
  },
  // 中国
  {
    code: 'CN',
    flag: '🇨🇳',
    text: '中国',
    regex: /(?:^|[^a-zA-Z])(?:CN|CHN|China)(?:[^a-zA-Z]|$)|中国|回国|国内|北京|上海|广州|深圳/i
  }
]

// 3. Cloudflare Anycast IP 段前缀
const CF_IP_PREFIXES = [
  '104.16.', '104.17.', '104.18.', '104.19.', '104.20.', '104.21.', '104.22.', '104.23.',
  '104.24.', '104.25.', '104.26.', '104.27.', '104.28.', '104.29.', '104.30.', '104.31.',
  '172.64.', '172.65.', '172.66.', '172.67.', '172.68.', '172.69.', '172.70.', '172.71.',
  '162.158.', '162.159.', '198.41.', '141.101.', '108.162.', '190.93.', '188.114.'
]

export function isCloudflare(name = '', server = '') {
  const s = String(server).trim().toLowerCase()
  const n = String(name).trim().toLowerCase()
  if (n.includes('cloudflare') || n.includes('cf官方') || n.includes('cf优选') || n.startsWith('cf')) {
    return true
  }
  return CF_IP_PREFIXES.some(prefix => s.startsWith(prefix))
}

/**
 * 获取节点的归属国家/区域信息（同步+带异步缓存）
 * @param {Object} node 节点对象 (包含 name, server 等)
 * @param {Object} ipCache IP/域名解析缓存字典
 * @returns {{ code: string, flag: string, text: string, fullText: string }}
 */
export function getNodeLocation(node, ipCache = {}) {
  if (!node) {
    return { code: 'UN', flag: '🌐', text: '未知区域', fullText: '未知区域' }
  }

  const name = String(node.name || '').trim()
  const server = String(node.server || '').trim()

  // 1. 优先检查异步 IP GeoIP 解析结果
  if (server && ipCache && ipCache[server]) {
    const geo = ipCache[server]
    if (geo && geo.country) {
      const cityPart = geo.city && geo.city !== geo.country ? ` · ${geo.city}` : ''
      const displayText = `${geo.country}${cityPart}`
      return {
        code: geo.countryCode || 'IP',
        flag: geo.flag || '🌐',
        text: displayText,
        fullText: `${geo.flag || '🌐'} ${geo.country}${cityPart}`
      }
    }
  }

  // 2. 检查国旗 Emoji
  for (const [flag, info] of Object.entries(EMOJI_FLAG_MAP)) {
    if (name.includes(flag)) {
      return {
        code: info.code,
        flag: info.flag,
        text: info.text,
        fullText: `${info.flag} ${info.text}`
      }
    }
  }

  // 3. 检查常见国家规则匹配（针对节点名称）
  for (const rule of LOCATION_RULES) {
    if (rule.regex.test(name)) {
      return {
        code: rule.code,
        flag: rule.flag,
        text: rule.text,
        fullText: `${rule.flag} ${rule.text}`
      }
    }
  }

  // 4. 检查 Cloudflare Anycast IP 段或名称
  if (isCloudflare(name, server)) {
    return {
      code: 'CF',
      flag: '🌐',
      text: 'Cloudflare Anycast',
      fullText: '🌐 Cloudflare Anycast'
    }
  }

  // 5. 检查节点服务器域名中的地域代号 (如 sg07.150239.xyz, hk.node.com)
  if (server) {
    for (const rule of LOCATION_RULES) {
      if (rule.regex.test(server)) {
        return {
          code: rule.code,
          flag: rule.flag,
          text: rule.text,
          fullText: `${rule.flag} ${rule.text}`
        }
      }
    }
  }

  // 6. 默认未识别标识
  return {
    code: 'UN',
    flag: '🌐',
    text: '未知区域',
    fullText: '🌐 未知区域'
  }
}
