local in_question = false
local in_answer = false
local in_analysis = false

local function raw(s)
  return pandoc.RawBlock("latex", s)
end

local function stringify_block(block)
  if block.content then
    return pandoc.utils.stringify(block.content)
  end
  return pandoc.utils.stringify(block)
end

local function close_question(out)
  if in_question then
    table.insert(out, raw("\\end{questionbox}"))
    in_question = false
  end
end

local function close_answer(out)
  if in_answer then
    table.insert(out, raw("\\end{answerbox}"))
    in_answer = false
  end
end

local function close_analysis(out)
  if in_analysis then
    table.insert(out, raw("\\end{analysisbox}"))
    in_analysis = false
  end
end

local function close_all(out)
  close_analysis(out)
  close_answer(out)
  close_question(out)
end

local function is_space(point)
  return point == 32 or point == 9 or point == 0x3000
end

local function is_digit(point)
  return (point >= 48 and point <= 57) or (point >= 0xFF10 and point <= 0xFF19)
end

local function is_question_delimiter(point)
  -- ASCII ".", fullwidth "．", or enumeration comma "、".
  return point == 46 or point == 0xFF0E or point == 0x3001
end

local function text_starts_question(text)
  if not text or utf8.len(text) == nil then
    return text ~= nil and text:match("^%s*%d+%s*%.") ~= nil
  end
  local index = 1
  local function point_at(pos)
    local offset = utf8.offset(text, pos)
    if not offset then
      return nil
    end
    return utf8.codepoint(text, offset)
  end
  local point = point_at(index)
  while point and is_space(point) do
    index = index + 1
    point = point_at(index)
  end
  local saw_digit = false
  while point and is_digit(point) do
    saw_digit = true
    index = index + 1
    point = point_at(index)
  end
  if not saw_digit then
    return false
  end
  while point and is_space(point) do
    index = index + 1
    point = point_at(index)
  end
  return is_question_delimiter(point)
end

local function starts_question(block)
  if block.t == "OrderedList" then
    return true
  end
  if block.t ~= "Para" and block.t ~= "Plain" then
    return false
  end
  return text_starts_question(stringify_block(block))
end

local function append_ordered_questions(out, block)
  for index, item in ipairs(block.content) do
    close_all(out)
    table.insert(out, raw("\\begin{questionbox}"))
    in_question = true
    local start_num = (block.start or 1) + index - 1
    table.insert(out, pandoc.OrderedList(
      {item},
      pandoc.ListAttributes(start_num, block.style, block.delimiter)
    ))
  end
end

local function starts_answer(block)
  if block.t ~= "Para" and block.t ~= "Plain" then
    return false
  end
  local text = stringify_block(block)
  return text:match("^%s*答案[：:]") ~= nil
end

local function starts_analysis(block)
  if block.t ~= "Para" and block.t ~= "Plain" then
    return false
  end
  local text = stringify_block(block)
  return text:match("^%s*解析[：:]") ~= nil
end

local function has_image(inlines)
  for _, inline in ipairs(inlines) do
    if inline.t == "Image" then
      return true
    end
  end
  return false
end

local function is_image_block(block)
  if block.t ~= "Para" and block.t ~= "Plain" then
    return false
  end
  return has_image(block.content)
end

function Pandoc(doc)
  local out = {}

  for i, block in ipairs(doc.blocks) do
    local next_block = doc.blocks[i + 1]
    if block.t == "Header" then
      if block.level <= 2 then
        close_all(out)
      end
      table.insert(out, block)
    elseif block.t == "HorizontalRule" then
      close_all(out)
    elseif starts_analysis(block) then
      close_question(out)
      close_answer(out)
      if not in_analysis then
        table.insert(out, raw("\\begin{analysisbox}"))
        in_analysis = true
      end
      table.insert(out, block)
    elseif starts_answer(block) then
      close_question(out)
      close_analysis(out)
      if not in_answer then
        table.insert(out, raw("\\begin{answerbox}"))
        in_answer = true
      end
      table.insert(out, block)
    elseif is_image_block(block) then
      if not in_question and next_block and (next_block.t == "HorizontalRule" or starts_question(next_block)) then
        close_analysis(out)
        close_answer(out)
      end
      table.insert(out, block)
    elseif block.t == "OrderedList" then
      append_ordered_questions(out, block)
    elseif starts_question(block) then
      close_all(out)
      table.insert(out, raw("\\begin{questionbox}"))
      in_question = true
      table.insert(out, block)
    else
      table.insert(out, block)
    end
  end

  close_all(out)
  return pandoc.Pandoc(out, doc.meta)
end
